import { Worker, type Job } from 'bullmq';
import { getRedis, QUEUE_NAMES } from './queue-client.js';
import { persistDeal, persistCsvBatch, persistJsonBatch } from '../ingestion/persistent-pipeline.js';
import { analyzeDeal } from '../agents/graphs/deal-analysis-graph.js';
import { classifyMarket } from '../agents/graphs/market-classification-graph.js';
import { recordOutcome } from '../agents/graphs/outcome-learning-graph.js';
import type {
  DealIngestionJobData,
  DealIngestionJobResult,
  BatchIngestionJobData,
  BatchIngestionJobResult,
  OutcomeLearningJobData,
  OutcomeLearningJobResult,
  MarketClassificationJobData,
  MarketClassificationJobResult,
} from './job-definitions.js';

const CONCURRENCY = parseInt(process.env.WORKER_CONCURRENCY ?? '3', 10);

// ─── Deal Ingestion Worker ────────────────────────────────────────────────────

export function startDealIngestionWorker() {
  return new Worker<DealIngestionJobData, DealIngestionJobResult>(
    QUEUE_NAMES.DEAL_INGESTION,
    async (job: Job<DealIngestionJobData>) => {
      const { raw, source, marketRegime } = job.data;
      const result = await persistDeal(raw, source, marketRegime);
      return {
        propertyId:   result.propertyId,
        simulationId: result.simulationId,
        errors:       result.errors,
        processingMs: result.processingMs,
      };
    },
    { connection: getRedis(), concurrency: CONCURRENCY },
  );
}

// ─── Batch Ingestion Worker ───────────────────────────────────────────────────

export function startBatchIngestionWorker() {
  return new Worker<BatchIngestionJobData, BatchIngestionJobResult>(
    QUEUE_NAMES.BATCH_INGESTION,
    async (job: Job<BatchIngestionJobData>) => {
      const { payload, format, source, marketRegime } = job.data;

      const result = format === 'csv'
        ? await persistCsvBatch(payload, source, marketRegime)
        : await persistJsonBatch(payload, source, marketRegime);

      await job.updateProgress(100);

      return { total: result.total, succeeded: result.succeeded, failed: result.failed };
    },
    { connection: getRedis(), concurrency: 1 }, // serial — batches can be large
  );
}

// ─── Outcome Learning Worker ──────────────────────────────────────────────────

export function startOutcomeLearningWorker() {
  return new Worker<OutcomeLearningJobData, OutcomeLearningJobResult>(
    QUEUE_NAMES.OUTCOME_LEARNING,
    async (job: Job<OutcomeLearningJobData>) => {
      const { outcome, propertyId, zip, buyerId, strategy } = job.data;
      const state = await recordOutcome(outcome, propertyId, zip, buyerId, strategy);
      return {
        weightVersion: state.weightVersion,
        mae:           state.mae,
        graphSynced:   state.graphSynced,
      };
    },
    { connection: getRedis(), concurrency: 1 }, // serial — weight updates must be ordered
  );
}

// ─── Market Classification Worker ────────────────────────────────────────────

export function startMarketClassificationWorker() {
  return new Worker<MarketClassificationJobData, MarketClassificationJobResult>(
    QUEUE_NAMES.MARKET_CLASSIFICATION,
    async (job: Job<MarketClassificationJobData>) => {
      const state = await classifyMarket(job.data);
      return {
        regime: state.regime,
        stored: state.stored,
        errors: state.errors,
      };
    },
    { connection: getRedis(), concurrency: CONCURRENCY },
  );
}

// ─── Start all workers ────────────────────────────────────────────────────────

export function startAllWorkers() {
  const workers = [
    startDealIngestionWorker(),
    startBatchIngestionWorker(),
    startOutcomeLearningWorker(),
    startMarketClassificationWorker(),
  ];

  for (const w of workers) {
    w.on('failed', (job, err) => {
      console.error(`[worker:${w.name}] job ${job?.id} failed:`, err.message);
    });
    w.on('completed', (job) => {
      console.log(`[worker:${w.name}] job ${job.id} completed`);
    });
  }

  return workers;
}
