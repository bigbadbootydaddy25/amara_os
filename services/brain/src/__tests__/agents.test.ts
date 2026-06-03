import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { Property } from '../types.js';

// ─── Mock all external I/O ────────────────────────────────────────────────────

vi.mock('../memory/postgres/weights-repo.js', () => ({
  WeightsRepo: {
    getLatest:      vi.fn().mockResolvedValue(null),
    save:           vi.fn().mockResolvedValue(undefined),
    recordOutcome:  vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock('../memory/postgres/property-repo.js', () => ({
  PropertyRepo: {
    findById: vi.fn().mockResolvedValue(null),
    create:   vi.fn().mockResolvedValue('mock-prop-id'),
  },
}));

vi.mock('../memory/postgres/simulation-repo.js', () => ({
  SimulationRepo: {
    create:                  vi.fn().mockResolvedValue('mock-sim-id'),
    findLatestForProperty:   vi.fn().mockResolvedValue(null),
  },
}));

vi.mock('../memory/qdrant/vector-store.js', () => ({
  searchProperties:   vi.fn().mockResolvedValue([]),
  searchMarketIntel:  vi.fn().mockResolvedValue([]),
  searchBuyers:       vi.fn().mockResolvedValue([]),
  upsertProperty:     vi.fn().mockResolvedValue(undefined),
  upsertMarketIntel:  vi.fn().mockResolvedValue(undefined),
  upsertBuyerSignal:  vi.fn().mockResolvedValue(undefined),
}));

vi.mock('../memory/neo4j/graph-sync.js', () => ({
  syncProperty:      vi.fn().mockResolvedValue(undefined),
  syncSimulation:    vi.fn().mockResolvedValue(undefined),
  syncDealOutcome:   vi.fn().mockResolvedValue(undefined),
  findBuyersForZip:  vi.fn().mockResolvedValue([]),
}));

vi.mock('../memory/neo4j/graph-client.js', () => ({
  runQuery:         vi.fn().mockResolvedValue({ records: [] }),
  getDriver:        vi.fn(),
  getSession:       vi.fn(),
  initConstraints:  vi.fn().mockResolvedValue(undefined),
  closeDriver:      vi.fn(),
}));

vi.mock('../memory/postgres/ingestion-log-repo.js', () => ({
  IngestionLogRepo: { log: vi.fn().mockResolvedValue(undefined) },
}));

// ─────────────────────────────────────────────────────────────────────────────

import { analyzeDeal } from '../agents/graphs/deal-analysis-graph.js';
import { classifyMarket } from '../agents/graphs/market-classification-graph.js';
import { recordOutcome } from '../agents/graphs/outcome-learning-graph.js';
import { classifyMarketRegime } from '../agents/tools/deal-tools.js';

const SAMPLE: Property = {
  id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  address: '999 Agent Test Blvd',
  city: 'Houston',
  state: 'TX',
  zip: '77001',
  askingPrice: 145_000,
  arvEstimate: 220_000,
  rehabEstimate: 22_000,
  conditionGrade: 6,
  taxDelinquent: true,
  vacant: true,
  ingestionSource: 'manual',
};

// ─── Market regime classifier (pure function, no mocks needed) ────────────────

describe('classifyMarketRegime', () => {
  it('classifies hot market', () => {
    expect(classifyMarketRegime({ zip: '77001', avgDom: 10, inventoryCount: 200 })).toBe('hot');
  });

  it('classifies cold market', () => {
    expect(classifyMarketRegime({ zip: '77001', avgDom: 90, inventoryCount: 3000 })).toBe('cold');
  });

  it('classifies distressed when foreclosure rate is high', () => {
    expect(classifyMarketRegime({ zip: '77001', foreclosureRate: 0.08 })).toBe('distressed');
  });

  it('defaults to neutral with no signals', () => {
    expect(classifyMarketRegime({ zip: '77001' })).toBe('neutral');
  });
});

// ─── Deal Analysis Graph ──────────────────────────────────────────────────────

describe('Deal Analysis Graph', () => {
  it('runs to completion and returns recommendation', async () => {
    const state = await analyzeDeal(SAMPLE, 'neutral');

    expect(state.recommendation).not.toBeNull();
    expect(['pursue', 'pass', 'needs_more_data']).toContain(state.recommendation?.action);
    expect(state.recommendation?.recommendedMao).toBeGreaterThan(0);
    expect(state.recommendation?.strategy).toBeTruthy();
  }, 10_000);

  it('returns a riskScore between 0 and 1', async () => {
    const state = await analyzeDeal(SAMPLE);
    expect(state.recommendation?.riskScore).toBeGreaterThanOrEqual(0);
    expect(state.recommendation?.riskScore).toBeLessThanOrEqual(1);
  }, 10_000);

  it('respects marketOverride', async () => {
    const hot  = await analyzeDeal(SAMPLE, 'hot');
    const cold = await analyzeDeal(SAMPLE, 'cold');
    expect(hot.marketRegime).toBe('hot');
    expect(cold.marketRegime).toBe('cold');
  }, 10_000);

  it('includes reasoning array with at least one entry', async () => {
    const state = await analyzeDeal(SAMPLE);
    expect(state.recommendation?.reasoning.length).toBeGreaterThan(0);
  }, 10_000);

  it('handles missing simulation gracefully', async () => {
    // simulation will work via DEFAULT_WEIGHTS fallback — just verify no crash
    const state = await analyzeDeal({ ...SAMPLE, arvEstimate: undefined, askingPrice: undefined });
    expect(state.recommendation).not.toBeNull();
  }, 10_000);
});

// ─── Market Classification Graph ─────────────────────────────────────────────

describe('Market Classification Graph', () => {
  it('classifies and stores market intel', async () => {
    const state = await classifyMarket({
      zip: '77001', avgDom: 12, inventoryCount: 300, medianArv: 225_000,
    });
    expect(state.regime).toBe('hot');
    expect(state.errors).toHaveLength(0);
  }, 10_000);

  it('handles upsert failure gracefully', async () => {
    const { upsertMarketIntel } = await import('../memory/qdrant/vector-store.js');
    vi.mocked(upsertMarketIntel).mockRejectedValueOnce(new Error('Qdrant down'));

    const state = await classifyMarket({ zip: '77002', avgDom: 90 });
    expect(state.stored).toBe(false);
    expect(state.errors.length).toBeGreaterThan(0);
  }, 10_000);
});

// ─── Outcome Learning Graph ───────────────────────────────────────────────────

describe('Outcome Learning Graph', () => {
  it('runs outcome learning and bumps weight version', async () => {
    const state = await recordOutcome(
      {
        dealId:              'deal-abc',
        actualContractPrice: 138_000,
        actualArv:           215_000,
        actualRehab:         28_000,
        actualDom:           18,
        actualProfit:        11_500,
        exitType:            'assigned',
        actualScenario:      'base',
      },
      'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      '77001',
    );

    expect(state.weightVersion).toBeTruthy();
    expect(state.mae).toBeGreaterThanOrEqual(0);
  }, 10_000);

  it('continues even if Neo4j sync fails', async () => {
    const { syncDealOutcome } = await import('../memory/neo4j/graph-sync.js');
    vi.mocked(syncDealOutcome).mockRejectedValueOnce(new Error('Neo4j timeout'));

    const state = await recordOutcome(
      {
        dealId: 'deal-xyz', actualContractPrice: 130_000,
        actualProfit: 9_000, exitType: 'assigned',
      },
      'prop-id', '77002',
    );

    expect(state.graphSynced).toBe(false);
    expect(state.weightVersion).toBeTruthy(); // weights still updated
  }, 10_000);
});
