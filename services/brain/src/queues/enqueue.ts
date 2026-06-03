/**
 * Public API for enqueuing brain jobs.
 * Import this from API routes — never import workers directly from Next.js.
 */

import { getQueue, QUEUE_NAMES } from './queue-client.js';
import type {
  DealIngestionJobData,
  BatchIngestionJobData,
  OutcomeLearningJobData,
  MarketClassificationJobData,
} from './job-definitions.js';

export async function enqueueDealIngestion(
  data: DealIngestionJobData,
  opts?: { priority?: number },
): Promise<string> {
  const job = await getQueue(QUEUE_NAMES.DEAL_INGESTION).add('ingest', data, {
    priority: opts?.priority ?? 5,
  });
  return job.id!;
}

export async function enqueueBatchIngestion(
  data: BatchIngestionJobData,
): Promise<string> {
  const job = await getQueue(QUEUE_NAMES.BATCH_INGESTION).add('batch', data, {
    priority: 10, // lower priority than single deals
  });
  return job.id!;
}

export async function enqueueOutcomeLearning(
  data: OutcomeLearningJobData,
): Promise<string> {
  const job = await getQueue(QUEUE_NAMES.OUTCOME_LEARNING).add('learn', data);
  return job.id!;
}

export async function enqueueMarketClassification(
  data: MarketClassificationJobData,
): Promise<string> {
  const job = await getQueue(QUEUE_NAMES.MARKET_CLASSIFICATION).add('classify', data);
  return job.id!;
}
