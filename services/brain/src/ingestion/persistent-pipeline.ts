import { randomUUID } from 'crypto';
import type {
  Property,
  IngestionResult,
  IngestionSource,
  MarketRegime,
  DealOutcomeInput,
} from '../types.js';
import { normalizeProperty } from './normalizers/property-normalizer.js';
import { parseCsv } from './parsers/csv-parser.js';
import { ingestJsonBatch as rawJsonBatch } from './ingestion-pipeline.js';
import { simulate, DEFAULT_WEIGHTS } from '../mirofish/engine/simulator.js';
import { updateWeights } from '../mirofish/learning/weight-updater.js';
import { PropertyRepo } from '../memory/postgres/property-repo.js';
import { SimulationRepo } from '../memory/postgres/simulation-repo.js';
import { WeightsRepo } from '../memory/postgres/weights-repo.js';
import { IngestionLogRepo } from '../memory/postgres/ingestion-log-repo.js';
import { syncProperty, syncSimulation } from '../memory/neo4j/graph-sync.js';
import { upsertProperty } from '../memory/qdrant/vector-store.js';
import { traceIngestion, traceLearning } from '../observability/tracer.js';
import { rememberDealSimulation, rememberDealOutcome } from '../memory/mem0/episodic-memory.js';
import { metrics } from '../telemetry/otel.js';

export function persistDeal(
  raw: Record<string, unknown>,
  source: IngestionSource,
  marketRegime: MarketRegime = 'neutral',
): Promise<IngestionResult> {
  return traceIngestion(source, () => _persistDeal(raw, source, marketRegime));
}

async function _persistDeal(
  raw: Record<string, unknown>,
  source: IngestionSource,
  marketRegime: MarketRegime,
): Promise<IngestionResult> {
  const start = Date.now();

  try {
    const { property, warnings } = normalizeProperty(raw, source);
    property.id = randomUUID();

    // Load weights (fallback to defaults if DB unavailable)
    const weights = await WeightsRepo.getLatest().catch(() => null) ?? DEFAULT_WEIGHTS;

    // Persist to Postgres
    const propertyId = await PropertyRepo.create(property);

    // Run simulation
    const sim = simulate({ ...property, id: propertyId }, weights, marketRegime);

    // Persist simulation
    const simRow = await SimulationRepo.create(sim);

    // Sync to Neo4j (non-fatal if Neo4j is down)
    await syncProperty({ ...property, id: propertyId }).catch((err: Error) =>
      console.warn('[neo4j] syncProperty failed:', err.message),
    );
    await syncSimulation(sim).catch((err: Error) =>
      console.warn('[neo4j] syncSimulation failed:', err.message),
    );

    // Upsert to Qdrant vector store (non-fatal)
    await upsertProperty({ ...property, id: propertyId }, sim).catch((err: Error) =>
      console.warn('[qdrant] upsertProperty failed:', err.message),
    );

    // Remember in episodic memory (non-fatal)
    await rememberDealSimulation({ ...property, id: propertyId }, sim).catch((err: Error) =>
      console.warn('[mem0] rememberDealSimulation failed:', err.message),
    );

    metrics.ingestTotal.inc();

    // Log ingestion
    await IngestionLogRepo.log({
      source,
      recordType: 'property',
      recordId: propertyId,
      status: 'success',
      processingMs: Date.now() - start,
    }).catch(() => undefined);

    return {
      success: true,
      propertyId,
      simulationId: simRow,
      errors: warnings,
      processingMs: Date.now() - start,
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);

    await IngestionLogRepo.log({
      source,
      recordType: 'property',
      status: 'error',
      rawInput: raw,
      errorMessage: message,
      processingMs: Date.now() - start,
    }).catch(() => undefined);

    metrics.ingestErrors.inc();

    return {
      success: false,
      errors: [message],
      processingMs: Date.now() - start,
    };
  }
}

export interface BatchResult {
  total: number;
  succeeded: number;
  failed: number;
  results: IngestionResult[];
}

export async function persistCsvBatch(
  csvText: string,
  source: IngestionSource,
  marketRegime: MarketRegime = 'neutral',
): Promise<BatchResult> {
  const { rows, errors: parseErrors } = parseCsv(csvText);
  const results: IngestionResult[] = [];

  for (const err of parseErrors) {
    results.push({ success: false, errors: [err], processingMs: 0 });
  }

  for (const row of rows) {
    results.push(await persistDeal(row as Record<string, unknown>, source, marketRegime));
  }

  return summary(results);
}

export async function persistJsonBatch(
  jsonText: string,
  source: IngestionSource,
  marketRegime: MarketRegime = 'neutral',
): Promise<BatchResult> {
  let items: unknown[];
  try {
    const parsed = JSON.parse(jsonText);
    items = Array.isArray(parsed) ? parsed : [parsed];
  } catch {
    return { total: 1, succeeded: 0, failed: 1, results: [{ success: false, errors: ['Invalid JSON'], processingMs: 0 }] };
  }

  const results: IngestionResult[] = [];
  for (const item of items) {
    if (typeof item !== 'object' || item === null) {
      results.push({ success: false, errors: ['Item not an object'], processingMs: 0 });
      continue;
    }
    results.push(await persistDeal(item as Record<string, unknown>, source, marketRegime));
  }

  return summary(results);
}

/**
 * Record deal outcome → update weights → persist new weights.
 */
export function recordOutcomeAndLearn(
  outcome: DealOutcomeInput,
  predictedMao: number,
  predictedArv: number,
  predictedRehab: number,
  zip: string,
): Promise<{ weightVersion: string; mae: number }> {
  return traceLearning(outcome.dealId, () =>
    _recordOutcomeAndLearn(outcome, predictedMao, predictedArv, predictedRehab, zip),
  );
}

async function _recordOutcomeAndLearn(
  outcome: DealOutcomeInput,
  predictedMao: number,
  predictedArv: number,
  predictedRehab: number,
  zip: string,
): Promise<{ weightVersion: string; mae: number }> {
  const current = await WeightsRepo.getLatest().catch(() => null) ?? DEFAULT_WEIGHTS;
  const { weights: updated, update } = updateWeights(
    current, outcome, predictedMao, predictedArv, predictedRehab, zip,
  );

  await WeightsRepo.save(updated);
  await WeightsRepo.recordOutcome(
    outcome.dealId,
    outcome.dealId, // property_id resolved by caller if different
    { mao: predictedMao, arv: predictedArv, rehab: predictedRehab, dom: 30, profit: 0 },
    {
      contractPrice: outcome.actualContractPrice,
      arv: outcome.actualArv,
      rehab: outcome.actualRehab,
      dom: outcome.actualDom,
      profit: outcome.actualProfit,
      scenario: outcome.actualScenario,
      modelVersion: updated.version,
    },
  );

  // Remember outcome in episodic memory (non-fatal)
  const prop = await PropertyRepo.findById(outcome.dealId).catch(() => null);
  if (prop) {
    await rememberDealOutcome(outcome, prop).catch((err: Error) =>
      console.warn('[mem0] rememberDealOutcome failed:', err.message),
    );
  }

  metrics.weightUpdates.inc();

  return { weightVersion: updated.version, mae: update.mae };
}

function summary(results: IngestionResult[]): BatchResult {
  return {
    total: results.length,
    succeeded: results.filter((r) => r.success).length,
    failed: results.filter((r) => !r.success).length,
    results,
  };
}
