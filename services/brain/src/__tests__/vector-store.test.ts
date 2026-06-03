import { describe, it, expect, vi, beforeEach } from 'vitest';
import { embedText, propertyToText, marketIntelToText, buyerSignalToText } from '../memory/qdrant/embedder.js';
import { VECTOR_SIZE } from '../memory/qdrant/qdrant-client.js';
import type { Property } from '../types.js';
import { simulate, DEFAULT_WEIGHTS } from '../mirofish/engine/simulator.js';

// Mock Qdrant client so vector-store tests run without a live server
vi.mock('../memory/qdrant/qdrant-client.js', async (importOriginal) => {
  const orig = await importOriginal<typeof import('../memory/qdrant/qdrant-client.js')>();
  return {
    ...orig,
    getQdrant: () => ({
      upsert:             vi.fn().mockResolvedValue({}),
      search:             vi.fn().mockResolvedValue([]),
      getCollections:     vi.fn().mockResolvedValue({ collections: [] }),
      createCollection:   vi.fn().mockResolvedValue({}),
      createPayloadIndex: vi.fn().mockResolvedValue({}),
    }),
  };
});

const SAMPLE: Property = {
  id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  address: '123 Vector Lane',
  city: 'Houston',
  state: 'TX',
  zip: '77001',
  askingPrice: 145_000,
  arvEstimate: 215_000,
  rehabEstimate: 20_000,
  conditionGrade: 6,
  taxDelinquent: true,
  vacant: false,
  ingestionSource: 'manual',
};

describe('Embedder', () => {
  it('returns a vector of the correct size', async () => {
    const vec = await embedText('3 bed 2 bath Houston TX 77001 ARV 215000');
    expect(vec).toHaveLength(VECTOR_SIZE);
  });

  it('is deterministic for the same input', async () => {
    const a = await embedText('test string');
    const b = await embedText('test string');
    expect(a).toEqual(b);
  });

  it('produces different vectors for different inputs', async () => {
    const a = await embedText('Houston TX 77001 ARV 200000');
    const b = await embedText('Dallas TX 75201 ARV 350000');
    const dot = a.reduce((s, v, i) => s + v * b[i], 0);
    // Different inputs → cosine similarity < 1
    expect(dot).toBeLessThan(0.999);
  });

  it('returns an L2-normalised vector', async () => {
    const vec = await embedText('any text');
    const norm = Math.sqrt(vec.reduce((s, v) => s + v * v, 0));
    expect(norm).toBeCloseTo(1.0, 4);
  });
});

describe('Text builders', () => {
  it('propertyToText includes key fields', () => {
    const text = propertyToText(SAMPLE);
    expect(text).toContain('77001');
    expect(text).toContain('Houston');
    expect(text).toContain('145');
    expect(text).toContain('tax delinquent');
  });

  it('propertyToText includes simulation when provided', () => {
    const sim = simulate(SAMPLE, DEFAULT_WEIGHTS, 'neutral');
    const text = propertyToText(SAMPLE, sim);
    expect(text).toContain('MAO');
    expect(text).toContain('risk');
  });

  it('marketIntelToText includes regime and ZIP', () => {
    const text = marketIntelToText({ zip: '77001', regime: 'hot', avgDom: 14 });
    expect(text).toContain('77001');
    expect(text).toContain('hot');
    expect(text).toContain('14');
  });

  it('buyerSignalToText includes buyer type and ZIPs', () => {
    const text = buyerSignalToText({
      name: 'John Smith',
      buyerType: 'cash',
      targetZips: ['77001', '77002'],
    });
    expect(text).toContain('cash');
    expect(text).toContain('77001');
  });
});

describe('Vector store (mocked Qdrant)', () => {
  it('upsertProperty resolves without error', async () => {
    const { upsertProperty } = await import('../memory/qdrant/vector-store.js');
    await expect(upsertProperty(SAMPLE)).resolves.toBeUndefined();
  });

  it('upsertProperty with simulation resolves', async () => {
    const { upsertProperty } = await import('../memory/qdrant/vector-store.js');
    const sim = simulate(SAMPLE, DEFAULT_WEIGHTS, 'neutral');
    await expect(upsertProperty(SAMPLE, sim)).resolves.toBeUndefined();
  });

  it('searchProperties returns array', async () => {
    const { searchProperties } = await import('../memory/qdrant/vector-store.js');
    const results = await searchProperties('3 bed Houston wholesale deal');
    expect(Array.isArray(results)).toBe(true);
  });

  it('searchMarketIntel returns array', async () => {
    const { searchMarketIntel } = await import('../memory/qdrant/vector-store.js');
    const results = await searchMarketIntel('hot market low inventory', { zip: '77001' });
    expect(Array.isArray(results)).toBe(true);
  });

  it('searchBuyers returns array', async () => {
    const { searchBuyers } = await import('../memory/qdrant/vector-store.js');
    const results = await searchBuyers('cash buyer Houston', { zip: '77001' });
    expect(Array.isArray(results)).toBe(true);
  });

  it('upsertMarketIntel resolves', async () => {
    const { upsertMarketIntel } = await import('../memory/qdrant/vector-store.js');
    await expect(
      upsertMarketIntel({ zip: '77001', regime: 'hot', medianArv: 220_000, avgDom: 14 }),
    ).resolves.toBeUndefined();
  });

  it('upsertBuyerSignal resolves', async () => {
    const { upsertBuyerSignal } = await import('../memory/qdrant/vector-store.js');
    await expect(
      upsertBuyerSignal({
        buyerId: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        name: 'Jane Cash',
        buyerType: 'cash',
        targetZips: ['77001', '77002'],
        minPrice: 100_000,
        maxPrice: 300_000,
      }),
    ).resolves.toBeUndefined();
  });
});

describe('Tracer', () => {
  it('traceIngestion runs fn and returns result', async () => {
    const { traceIngestion } = await import('../observability/tracer.js');
    const result = await traceIngestion('manual', async () => ({ success: true }));
    expect(result).toEqual({ success: true });
  });

  it('traceSimulation runs fn and returns result', async () => {
    const { traceSimulation } = await import('../observability/tracer.js');
    const result = await traceSimulation('prop-123', async () => 'done');
    expect(result).toBe('done');
  });

  it('traceLearning propagates errors', async () => {
    const { traceLearning } = await import('../observability/tracer.js');
    await expect(
      traceLearning('deal-x', async () => { throw new Error('learning failed'); }),
    ).rejects.toThrow('learning failed');
  });

  it('traceRetrieval runs fn', async () => {
    const { traceRetrieval } = await import('../observability/tracer.js');
    const out = await traceRetrieval('cheap house houston', 'properties', async () => [1, 2, 3]);
    expect(out).toEqual([1, 2, 3]);
  });
});
