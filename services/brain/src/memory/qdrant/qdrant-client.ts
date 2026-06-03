import { QdrantClient } from '@qdrant/js-client-rest';

let client: QdrantClient | null = null;

export const COLLECTIONS = {
  PROPERTIES:    'amara_properties',
  MARKET_INTEL:  'amara_market_intel',
  BUYER_SIGNALS: 'amara_buyer_signals',
} as const;

export const VECTOR_SIZE = 384; // sentence-transformers/all-MiniLM-L6-v2 compatible

export function getQdrant(): QdrantClient {
  if (!client) {
    client = new QdrantClient({
      host: process.env.QDRANT_HOST ?? 'localhost',
      port: parseInt(process.env.QDRANT_PORT ?? '6333', 10),
    });
  }
  return client;
}

export async function ensureCollections(): Promise<void> {
  const q = getQdrant();
  const { collections } = await q.getCollections();
  const existing = new Set(collections.map((c) => c.name));

  for (const name of Object.values(COLLECTIONS)) {
    if (existing.has(name)) continue;
    await q.createCollection(name, {
      vectors: {
        size:     VECTOR_SIZE,
        distance: 'Cosine',
      },
      optimizers_config: { default_segment_number: 2 },
      replication_factor: 1,
    });

    // Create payload indexes for fast filtering
    if (name === COLLECTIONS.PROPERTIES) {
      await q.createPayloadIndex(name, { field_name: 'zip',   field_schema: 'keyword' });
      await q.createPayloadIndex(name, { field_name: 'state', field_schema: 'keyword' });
      await q.createPayloadIndex(name, { field_name: 'arv_estimate', field_schema: 'float' });
      await q.createPayloadIndex(name, { field_name: 'risk_score',   field_schema: 'float' });
    }

    if (name === COLLECTIONS.MARKET_INTEL) {
      await q.createPayloadIndex(name, { field_name: 'zip',    field_schema: 'keyword' });
      await q.createPayloadIndex(name, { field_name: 'regime', field_schema: 'keyword' });
    }

    if (name === COLLECTIONS.BUYER_SIGNALS) {
      await q.createPayloadIndex(name, { field_name: 'zip',        field_schema: 'keyword' });
      await q.createPayloadIndex(name, { field_name: 'buyer_type', field_schema: 'keyword' });
    }
  }
}
