import { describe, it, expect } from 'vitest';
import { runAcquisitionScoutAgent } from '../agents/graphs/acquisition-scout-graph.js';
import { runDispositionMatcherAgent } from '../agents/graphs/disposition-matcher-graph.js';
import { runDealNegotiatorAgent } from '../agents/graphs/deal-negotiator-graph.js';
import { runAcquisitionScout, runDispositionMatcher, runDealNegotiator } from '../agents/tools/hermes-tools.js';
import type { Property } from '../types.js';

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const PROPERTY: Property = {
  id:              'hermes-prop-1',
  address:         '456 Test Ave',
  city:            'Tulsa',
  state:           'OK',
  zip:             '74101',
  beds:            3,
  baths:           2,
  sqft:            1500,
  yearBuilt:       1990,
  condition:       'fair',
  arvEstimate:     220_000,
  listPrice:       160_000,
  rehabEstimate:   35_000,
  ingestionSource: 'manual',
};

const HIGH_RISK_PROPERTY: Property = {
  ...PROPERTY,
  id:          'hermes-prop-2',
  arvEstimate: 120_000,
  listPrice:   115_000,   // almost no room
  rehabEstimate: 50_000,  // heavy rehab
};

// ─── Hermes Tools (unit) ──────────────────────────────────────────────────────

describe('Hermes Tools — Acquisition Scout', () => {
  it('returns green verdict for a solid deal', async () => {
    const result = await runAcquisitionScout({ property: PROPERTY, marketRegime: 'neutral' });
    expect(['green', 'yellow', 'red']).toContain(result.verdict);
    expect(result.simulation.recommendedMao).toBeGreaterThan(0);
    expect(result.verdictReason).toBeTruthy();
  });

  it('returns red or yellow for a marginal deal', async () => {
    const result = await runAcquisitionScout({ property: HIGH_RISK_PROPERTY, marketRegime: 'cold' });
    expect(['yellow', 'red']).toContain(result.verdict);
  });

  it('includes prior deals and market context arrays', async () => {
    const result = await runAcquisitionScout({ property: PROPERTY });
    expect(Array.isArray(result.priorDeals)).toBe(true);
    expect(Array.isArray(result.marketContext)).toBe(true);
  });
});

describe('Hermes Tools — Disposition Matcher', () => {
  it('returns matcher output with buyers array', async () => {
    const result = await runDispositionMatcher({
      zip: '74101', strategy: 'wholesale', mao: 130_000, arv: 220_000,
    });
    expect(typeof result.totalFound).toBe('number');
    expect(Array.isArray(result.buyers)).toBe(true);
    expect(result.recommendation).toBeTruthy();
  });

  it('recommendation mentions ZIP when no buyers found', async () => {
    const result = await runDispositionMatcher({
      zip: '00000', strategy: 'wholesale', mao: 100_000, arv: 200_000,
    });
    expect(result.totalFound).toBe(0);
    expect(result.recommendation).toContain('00000');
  });
});

describe('Hermes Tools — Deal Negotiator', () => {
  it('recommends counter when seller ask is above MAO but below ceiling', async () => {
    // ARV 220k, rehab 35k → MAO roughly in 120-140k range
    // Seller ask at 145k should trigger a counter
    const result = await runDealNegotiator({
      property:     PROPERTY,
      currentOffer: 120_000,
      sellerAsk:    145_000,
      marketRegime: 'neutral',
    });
    expect(typeof result.shouldCounter).toBe('boolean');
    expect(result.counterRange.floor).toBeGreaterThan(0);
    expect(result.counterRange.target).toBeGreaterThanOrEqual(result.counterRange.floor);
    expect(result.counterRange.ceiling).toBeGreaterThanOrEqual(result.counterRange.target);
    expect(result.rationale).toBeTruthy();
  });

  it('does not counter when seller ask is at or below MAO', async () => {
    // Use a very low seller ask (75k) that will always be below any MiroFish MAO
    const result = await runDealNegotiator({
      property:     PROPERTY,
      currentOffer: 70_000,
      sellerAsk:    75_000,
      marketRegime: 'neutral',
    });
    expect(result.shouldCounter).toBe(false);
    expect(result.rationale).toMatch(/accept|within/i);
  });

  it('does not counter when seller ask far exceeds ceiling', async () => {
    const result = await runDealNegotiator({
      property:     HIGH_RISK_PROPERTY,
      currentOffer: 80_000,
      sellerAsk:    119_000,  // near ARV for a distressed deal
      marketRegime: 'cold',
    });
    expect(result.shouldCounter).toBe(false);
  });

  it('counter range is internally consistent', async () => {
    const result = await runDealNegotiator({
      property:     PROPERTY,
      currentOffer: 100_000,
      sellerAsk:    140_000,
    });
    expect(result.counterRange.floor).toBeLessThanOrEqual(result.counterRange.target);
    expect(result.counterRange.target).toBeLessThanOrEqual(result.counterRange.ceiling);
  });
});

// ─── Hermes Agent Graphs (integration) ───────────────────────────────────────

describe('Acquisition Scout Agent Graph', () => {
  it('runs full graph and returns a verdict', async () => {
    const result = await runAcquisitionScoutAgent(PROPERTY);
    expect(['green', 'yellow', 'red', 'error']).toContain(result.verdict);
    expect(result.summary).toBeTruthy();
    expect(result.summary).toContain('MAO');
  });

  it('summary contains ARV', async () => {
    const result = await runAcquisitionScoutAgent(PROPERTY);
    expect(result.summary).toContain('ARV');
  });
});

describe('Disposition Matcher Agent Graph', () => {
  it('runs full graph and returns a summary', async () => {
    const result = await runDispositionMatcherAgent({
      propertyId: 'hermes-prop-1',
      zip:        '74101',
      mao:        130_000,
      arv:        220_000,
      strategy:   'wholesale',
    });
    expect(typeof result.totalBuyers).toBe('number');
    expect(result.summary).toBeTruthy();
  });
});

describe('Deal Negotiator Agent Graph', () => {
  it('runs full graph and returns counter guidance', async () => {
    const result = await runDealNegotiatorAgent({
      property:     PROPERTY,
      currentOffer: 120_000,
      sellerAsk:    145_000,
    });
    expect(typeof result.shouldCounter).toBe('boolean');
    expect(result.summary).toBeTruthy();
    expect(result.summary).toMatch(/floor|target|ceiling/i);
  });
});
