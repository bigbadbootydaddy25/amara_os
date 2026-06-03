import { Queue, Worker, type Job } from 'bullmq';
import Redis from 'ioredis';

let connection: Redis | null = null;

export function getRedis(): Redis {
  if (!connection) {
    connection = new Redis(process.env.REDIS_URL ?? 'redis://localhost:6379', {
      maxRetriesPerRequest: null, // required by BullMQ
      enableReadyCheck: false,
      password: process.env.REDIS_PASSWORD ?? 'amara_redis_secret',
    });
  }
  return connection;
}

export const QUEUE_NAMES = {
  DEAL_INGESTION:       'deal-ingestion',
  BATCH_INGESTION:      'batch-ingestion',
  OUTCOME_LEARNING:     'outcome-learning',
  MARKET_CLASSIFICATION: 'market-classification',
} as const;

export type QueueName = typeof QUEUE_NAMES[keyof typeof QUEUE_NAMES];

const queues = new Map<string, Queue>();

export function getQueue(name: QueueName): Queue {
  if (!queues.has(name)) {
    queues.set(name, new Queue(name, {
      connection: getRedis(),
      defaultJobOptions: {
        attempts:    3,
        backoff:     { type: 'exponential', delay: 2_000 },
        removeOnComplete: { count: 500 },
        removeOnFail:     { count: 100 },
      },
    }));
  }
  return queues.get(name)!;
}

export async function closeQueues(): Promise<void> {
  for (const q of queues.values()) await q.close();
  queues.clear();
  if (connection) { connection.disconnect(); connection = null; }
}
