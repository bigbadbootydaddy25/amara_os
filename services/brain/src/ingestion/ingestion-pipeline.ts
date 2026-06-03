import { randomUUID } from 'crypto';
import type {
  Property,
  IngestionResult,
  IngestionSource,
  MiroFishWeights,
  MarketRegime,
} from '../types.js';
import { normalizeProperty } from './normalizers/property-normalizer.js';
import { parseCsv } from './parsers/csv-parser.js';
import { simulate, DEFAULT_WEIGHTS } from '../mirofish/engine/simulator.js';

export interface PipelineOptions {
  source: IngestionSource;
  weights?: MiroFishWeights;
  marketRegime?: MarketRegime;
  onPropertySaved?: (property: Property) => Promise<string>;
  onSimulationSaved?: (result: ReturnType<typeof simulate>) => Promise<string>;
}

// ─────────────────────────────────────────────
// SINGLE DEAL INGESTION
// ─────────────────────────────────────────────

export async function ingestDeal(
  raw: Record<string, unknown>,
  options: PipelineOptions,
): Promise<IngestionResult> {
  const start = Date.now();

  try {
    const { property, warnings } = normalizeProperty(raw, options.source);
    property.id = randomUUID();

    const propertyId = options.onPropertySaved
      ? await options.onPropertySaved(property)
      : property.id;

    const weights = options.weights ?? DEFAULT_WEIGHTS;
    const regime = options.marketRegime ?? 'neutral';
    const simulation = simulate({ ...property, id: propertyId }, weights, regime);

    const simulationId = options.onSimulationSaved
      ? await options.onSimulationSaved(simulation)
      : simulation.propertyId;

    return {
      success: true,
      propertyId,
      simulationId,
      errors: warnings,
      processingMs: Date.now() - start,
    };
  } catch (err) {
    return {
      success: false,
      errors: [err instanceof Error ? err.message : String(err)],
      processingMs: Date.now() - start,
    };
  }
}

// ─────────────────────────────────────────────
// CSV BATCH INGESTION
// ─────────────────────────────────────────────

export interface BatchIngestionResult {
  total: number;
  succeeded: number;
  failed: number;
  results: IngestionResult[];
}

export async function ingestCsvBatch(
  csvText: string,
  options: PipelineOptions,
): Promise<BatchIngestionResult> {
  const { rows, errors: parseErrors } = parseCsv(csvText);

  const results: IngestionResult[] = [];

  // Log parse errors as failed entries
  for (const err of parseErrors) {
    results.push({ success: false, errors: [err], processingMs: 0 });
  }

  for (const row of rows) {
    const result = await ingestDeal(row as Record<string, unknown>, options);
    results.push(result);
  }

  return {
    total: results.length,
    succeeded: results.filter((r) => r.success).length,
    failed: results.filter((r) => !r.success).length,
    results,
  };
}

// ─────────────────────────────────────────────
// JSON BATCH INGESTION
// ─────────────────────────────────────────────

export async function ingestJsonBatch(
  jsonText: string,
  options: PipelineOptions,
): Promise<BatchIngestionResult> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(jsonText);
  } catch {
    return {
      total: 0,
      succeeded: 0,
      failed: 1,
      results: [{ success: false, errors: ['Invalid JSON'], processingMs: 0 }],
    };
  }

  const items = Array.isArray(parsed) ? parsed : [parsed];
  const results: IngestionResult[] = [];

  for (const item of items) {
    if (typeof item !== 'object' || item === null) {
      results.push({
        success: false,
        errors: ['Item is not an object'],
        processingMs: 0,
      });
      continue;
    }
    const result = await ingestDeal(item as Record<string, unknown>, options);
    results.push(result);
  }

  return {
    total: results.length,
    succeeded: results.filter((r) => r.success).length,
    failed: results.filter((r) => !r.success).length,
    results,
  };
}
