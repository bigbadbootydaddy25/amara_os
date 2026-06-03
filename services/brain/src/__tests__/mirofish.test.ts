import { describe, it, expect } from 'vitest';
import { simulate, DEFAULT_WEIGHTS } from '../mirofish/engine/simulator.js';
import { computeFeatures } from '../mirofish/features/feature-engine.js';
import { runScenario } from '../mirofish/scenarios/scenario-engine.js';
import { updateWeights } from '../mirofish/learning/weight-updater.js';
import type { Property, MiroFishWeights } from '../types.js';

const BASE_PROPERTY: Property = {
  address: '1234 Main St',
  city: 'Houston',
  state: 'TX',
  zip: '77001',
  askingPrice: 140_000,
  arvEstimate: 220_000,
  arvLow: 205_000,
  arvHigh: 235_000,
  rehabEstimate: 25_000,
  bedrooms: 3,
  bathrooms: 2,
  sqft: 1400,
  yearBuilt: 1985,
  conditionGrade: 5,
  taxDelinquent: true,
  vacant: true,
  ingestionSource: 'manual',
};

describe('MiroFish — Feature Engine', () => {
  it('computes features from a property', () => {
    const features = computeFeatures(BASE_PROPERTY, DEFAULT_WEIGHTS, 'neutral');
    expect(features.arvMidpoint).toBe(220_000);
    expect(features.discountDepth).toBeGreaterThan(0);
    expect(features.discountDepth).toBeLessThanOrEqual(1);
    expect(features.distressScore).toBeGreaterThan(0); // taxDelinquent + vacant
    expect(features.maoCeiling).toBeGreaterThan(0);
    expect(features.liquidityScore).toBeGreaterThan(0);
    expect(features.liquidityScore).toBeLessThanOrEqual(1);
  });

  it('distress score increases with more flags', () => {
    const base = computeFeatures(BASE_PROPERTY, DEFAULT_WEIGHTS, 'neutral');
    const heavily_distressed = computeFeatures(
      { ...BASE_PROPERTY, bankruptcy: true, liens: true, preForeclosure: true },
      DEFAULT_WEIGHTS,
      'neutral',
    );
    expect(heavily_distressed.distressScore).toBeGreaterThan(base.distressScore);
  });

  it('discount depth = 0 when asking === ARV', () => {
    const features = computeFeatures(
      { ...BASE_PROPERTY, askingPrice: 220_000 },
      DEFAULT_WEIGHTS,
      'neutral',
    );
    expect(features.discountDepth).toBeCloseTo(0, 2);
  });

  it('liquidity is higher in hot market vs cold', () => {
    const hot = computeFeatures(BASE_PROPERTY, DEFAULT_WEIGHTS, 'hot');
    const cold = computeFeatures(BASE_PROPERTY, DEFAULT_WEIGHTS, 'cold');
    expect(hot.liquidityScore).toBeGreaterThan(cold.liquidityScore);
  });
});

describe('MiroFish — Scenario Engine', () => {
  const features = computeFeatures(BASE_PROPERTY, DEFAULT_WEIGHTS, 'neutral');

  it('runs all three scenarios', () => {
    const c = runScenario(features, 'conservative');
    const b = runScenario(features, 'base');
    const a = runScenario(features, 'aggressive');

    expect(c.scenario).toBe('conservative');
    expect(b.scenario).toBe('base');
    expect(a.scenario).toBe('aggressive');

    expect(c.mao).toBeGreaterThan(0);
    expect(b.mao).toBeGreaterThan(0);
    expect(a.mao).toBeGreaterThan(0);
  });

  it('conservative MAO ≤ base MAO ≤ aggressive MAO', () => {
    const c = runScenario(features, 'conservative');
    const b = runScenario(features, 'base');
    const a = runScenario(features, 'aggressive');
    expect(c.mao).toBeLessThanOrEqual(b.mao);
    expect(b.mao).toBeLessThanOrEqual(a.mao);
  });

  it('risk scores: conservative risk > aggressive risk', () => {
    const c = runScenario(features, 'conservative');
    const a = runScenario(features, 'aggressive');
    expect(c.riskScore).toBeGreaterThan(a.riskScore);
  });

  it('scenario outputs include strategy and reasoning', () => {
    const b = runScenario(features, 'base');
    expect(b.strategy).toBeTruthy();
    expect(b.reasoning).toContain('[BASE]');
  });

  it('MAOs are rounded to nearest $500', () => {
    const b = runScenario(features, 'base');
    expect(b.mao % 500).toBe(0);
  });
});

describe('MiroFish — Full Simulation', () => {
  it('produces a complete simulation result', () => {
    const result = simulate(BASE_PROPERTY, DEFAULT_WEIGHTS, 'neutral');
    expect(result.conservative).toBeTruthy();
    expect(result.base).toBeTruthy();
    expect(result.aggressive).toBeTruthy();
    expect(result.recommendedMao).toBeGreaterThan(0);
    expect(result.recommendedMao % 500).toBe(0);
    expect(result.riskScore).toBeGreaterThanOrEqual(0);
    expect(result.riskScore).toBeLessThanOrEqual(1);
    expect(result.confidenceScore).toBeGreaterThanOrEqual(0);
    expect(result.modelVersion).toBe('v1.0.0');
  });

  it('recommended MAO is conservative-weighted', () => {
    const result = simulate(BASE_PROPERTY, DEFAULT_WEIGHTS, 'neutral');
    expect(result.recommendedMao).toBeLessThanOrEqual(result.base.mao);
  });

  it('simulation handles missing ARV gracefully', () => {
    const noArv: Property = { ...BASE_PROPERTY, arvEstimate: undefined, arvLow: undefined, arvHigh: undefined };
    expect(() => simulate(noArv, DEFAULT_WEIGHTS, 'neutral')).not.toThrow();
  });

  it('assigns propertyId', () => {
    const result = simulate(BASE_PROPERTY, DEFAULT_WEIGHTS, 'neutral');
    expect(result.propertyId).toBeTruthy();
  });
});

describe('MiroFish — Learning Loop', () => {
  it('updates weights from outcome without mutating original', () => {
    const original = { ...DEFAULT_WEIGHTS };
    const outcome = {
      dealId: 'deal-1',
      actualContractPrice: 135_000,
      actualArv: 215_000,
      actualRehab: 30_000,
      actualDom: 22,
      actualProfit: 12_000,
      exitType: 'assigned' as const,
    };

    const { weights: updated, update } = updateWeights(
      DEFAULT_WEIGHTS,
      outcome,
      145_000,
      220_000,
      25_000,
      '77001',
    );

    expect(updated).not.toBe(original);
    expect(updated.version).not.toBe(DEFAULT_WEIGHTS.version);
    expect(updated.trainingSamples).toBe(DEFAULT_WEIGHTS.trainingSamples + 1);
    expect(update.mae).toBeGreaterThanOrEqual(0);
  });

  it('builds ZIP priors after first outcome', () => {
    const outcome = {
      dealId: 'deal-2',
      actualContractPrice: 130_000,
      actualArv: 215_000,
      actualDom: 18,
      actualProfit: 9_500,
      exitType: 'assigned' as const,
    };

    const { weights } = updateWeights(DEFAULT_WEIGHTS, outcome, 140_000, 220_000, 25_000, '77002');
    expect(weights.zipPriors['77002']).toBeTruthy();
    expect(weights.zipPriors['77002'].sampleCount).toBe(1);
  });

  it('version increments monotonically across updates', () => {
    let w: MiroFishWeights = DEFAULT_WEIGHTS;
    for (let i = 0; i < 3; i++) {
      const outcome = {
        dealId: `deal-${i}`,
        actualContractPrice: 130_000 + i * 1_000,
        actualProfit: 10_000,
        exitType: 'assigned' as const,
      };
      const { weights } = updateWeights(w, outcome, 140_000, 220_000, 25_000, '77001');
      expect(weights.version > w.version).toBe(true);
      w = weights;
    }
  });
});
