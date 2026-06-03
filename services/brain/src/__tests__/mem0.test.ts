import { describe, it, expect, beforeEach } from 'vitest';
import {
  rememberFact,
  searchMemory,
  getAllMemories,
  forgetMemory,
  rememberDealSimulation,
  rememberDealOutcome,
  rememberMarketCondition,
  recallDealsInZip,
  recallMarketContext,
} from '../memory/mem0/episodic-memory.js';
import type { Property, SimulationResult, DealOutcomeInput } from '../types.js';

// MEM0_API_KEY is not set in test env → uses local in-process store

const USER = 'test_user_' + Date.now(); // isolated namespace per test run

const PROPERTY: Property = {
  id: 'prop-1',
  address: '123 Main St',
  city: 'Oklahoma City',
  state: 'OK',
  zip: '73101',
  beds: 3,
  baths: 2,
  sqft: 1400,
  yearBuilt: 1985,
  condition: 'fair',
  arvEstimate: 200_000,
  listPrice: 140_000,
  rehabEstimate: 30_000,
  source: 'manual',
};

const SIM: SimulationResult = {
  propertyId: 'prop-1',
  recommendedMao:      110_000,
  recommendedStrategy: 'wholesale',
  riskScore:           0.3,
  confidenceScore:     0.75,
  features: {
    arvMidpoint:          200_000,
    discountDepth:        0.45,
    rehabRisk:            0.25,
    liquidityScore:       0.7,
    buyerDemandHeat:      0.65,
    exitVelocity:         0.6,
    distressScore:        0.5,
    assignmentProbability:0.8,
    maoCeiling:           120_000,
    marketRegime:         'neutral',
  },
  base:         { mao: 110_000, roi: [0.2, 0.3], riskScore: 0.3, strategy: 'wholesale', reasoning: '' },
  conservative: { mao: 100_000, roi: [0.15, 0.25], riskScore: 0.4, strategy: 'wholesale', reasoning: '' },
  aggressive:   { mao: 120_000, roi: [0.25, 0.35], riskScore: 0.2, strategy: 'wholesale', reasoning: '' },
};

describe('Episodic Memory — Local Store', () => {
  it('stores and retrieves a fact', async () => {
    const id = await rememberFact('Test fact about 73101 market', USER);
    expect(typeof id).toBe('string');
    expect(id.length).toBeGreaterThan(0);

    const all = await getAllMemories(USER);
    expect(all.some((m) => m.id === id)).toBe(true);
  });

  it('searches memories by keyword', async () => {
    await rememberFact('Deal closed in ZIP 73102 for $150k profit', USER);
    const results = await searchMemory('73102 profit', USER, 5);
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].score).toBeGreaterThanOrEqual(0);
  });

  it('forgets a memory by id', async () => {
    const id = await rememberFact('Temporary fact to forget', USER);
    await forgetMemory(id, USER);
    const all = await getAllMemories(USER);
    expect(all.some((m) => m.id === id)).toBe(false);
  });

  it('returns empty array when no memories', async () => {
    const results = await getAllMemories('empty_user_' + Date.now());
    expect(results).toEqual([]);
  });

  it('search returns results sorted by score descending', async () => {
    const u = 'search_sort_' + Date.now();
    await rememberFact('Market condition for ZIP 73103 is hot seller', u);
    await rememberFact('Something unrelated about apples', u);
    await rememberFact('ZIP 73103 high demand properties', u);
    const results = await searchMemory('ZIP 73103', u, 5);
    expect(results.length).toBeGreaterThanOrEqual(2);
    for (let i = 1; i < results.length; i++) {
      expect(results[i - 1].score).toBeGreaterThanOrEqual(results[i].score);
    }
  });

  it('stores metadata with a fact', async () => {
    const meta = { type: 'deal_simulation', zip: '73104' };
    const id = await rememberFact('Deal in 73104', USER, meta);
    const all = await getAllMemories(USER);
    const found = all.find((m) => m.id === id);
    expect(found?.metadata).toMatchObject(meta);
  });
});

describe('Domain Memory Writers', () => {
  const u = 'domain_' + Date.now();

  it('rememberDealSimulation stores a formatted fact', async () => {
    await rememberDealSimulation(PROPERTY, SIM, u);
    const all = await getAllMemories(u);
    expect(all.length).toBe(1);
    expect(all[0].memory).toContain('123 Main St');
    expect(all[0].memory).toContain('ARV');
    expect(all[0].metadata?.type).toBe('deal_simulation');
    expect(all[0].metadata?.zip).toBe('73101');
  });

  it('rememberDealOutcome stores outcome fact', async () => {
    const outcome: DealOutcomeInput = {
      dealId:               'deal-1',
      actualContractPrice:  105_000,
      actualProfit:         22_000,
      actualArv:            198_000,
      actualRehab:          31_000,
      actualDom:            25,
      exitType:             'wholesale',
      actualScenario:       'base',
    };
    await rememberDealOutcome(outcome, PROPERTY, u);
    const all = await getAllMemories(u);
    const outcome_mem = all.find((m) => m.metadata?.type === 'deal_outcome');
    expect(outcome_mem).toBeDefined();
    expect(outcome_mem?.memory).toContain('123 Main St');
    expect(outcome_mem?.memory).toContain('Profit');
  });

  it('rememberMarketCondition stores market fact', async () => {
    await rememberMarketCondition('73101', 'hot_seller', 'High absorption rate, low DOM.', u);
    const all = await getAllMemories(u);
    const market_mem = all.find((m) => m.metadata?.type === 'market_condition');
    expect(market_mem).toBeDefined();
    expect(market_mem?.memory).toContain('73101');
    expect(market_mem?.memory).toContain('hot_seller');
  });
});

describe('Domain Memory Readers', () => {
  const u = 'readers_' + Date.now();

  beforeEach(async () => {
    await rememberDealSimulation(PROPERTY, SIM, u);
    await rememberMarketCondition('73101', 'neutral', 'Stable prices.', u);
  });

  it('recallDealsInZip finds deal for zip', async () => {
    const results = await recallDealsInZip('73101', u);
    expect(results.length).toBeGreaterThan(0);
  });

  it('recallMarketContext finds market condition for zip', async () => {
    const results = await recallMarketContext('73101', u);
    expect(results.length).toBeGreaterThan(0);
  });
});
