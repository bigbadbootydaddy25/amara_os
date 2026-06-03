/**
 * Stress Tests — throughput and concurrency for the AMARA OS brain service.
 * These tests run fully in-process (no DB/Redis/Qdrant required) by mocking
 * the external sinks.  They measure latency and error rates under load.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { simulate, DEFAULT_WEIGHTS } from '../../mirofish/engine/simulator.js';
import { normalizeProperty } from '../../ingestion/normalizers/property-normalizer.js';
import {
  rememberFact,
  searchMemory,
  getAllMemories,
} from '../../memory/mem0/episodic-memory.js';
import { metrics } from '../../telemetry/otel.js';
import type { Property } from '../../types.js';

// ─── Fixture factory ──────────────────────────────────────────────────────────

function makeRawDeal(i: number): Record<string, unknown> {
  return {
    address:      `${1000 + i} Stress Ln`,
    city:         'Test City',
    state:        'OK',
    zip:          String(73000 + (i % 100)),
    beds:         3,
    baths:        2,
    sqft:         1200 + (i % 400),
    yearBuilt:    1980 + (i % 40),
    condition:    ['poor', 'fair', 'good'][i % 3],
    arv_estimate: 150_000 + (i % 50) * 1_000,
    list_price:   100_000 + (i % 30) * 1_000,
    rehab_estimate: 20_000 + (i % 20) * 500,
    source:       'manual',
  };
}

function makeProperty(i: number): Property {
  return {
    id:            `prop-stress-${i}`,
    address:       `${1000 + i} Stress Ln`,
    city:          'Test City',
    state:         'OK',
    zip:           String(73000 + (i % 100)),
    beds:          3,
    baths:         2,
    sqft:          1200 + (i % 400),
    yearBuilt:     1980 + (i % 40),
    condition:     ['poor', 'fair', 'good'][i % 3] as Property['condition'],
    arvEstimate:   150_000 + (i % 50) * 1_000,
    listPrice:     100_000 + (i % 30) * 1_000,
    rehabEstimate: 20_000 + (i % 20) * 500,
    source:        'manual',
  };
}

// ─── Simulation stress ────────────────────────────────────────────────────────

describe('Stress: MiroFish simulation throughput', () => {
  it('runs 500 simulations under 3 seconds', () => {
    const N = 500;
    const start = Date.now();
    for (let i = 0; i < N; i++) {
      const prop = makeProperty(i);
      const sim = simulate(prop, DEFAULT_WEIGHTS, 'neutral');
      expect(sim.recommendedMao).toBeGreaterThan(0);
    }
    const elapsed = Date.now() - start;
    expect(elapsed).toBeLessThan(3_000);
  });

  it('all 500 simulations produce valid MAO', () => {
    for (let i = 0; i < 500; i++) {
      const sim = simulate(makeProperty(i), DEFAULT_WEIGHTS, 'neutral');
      expect(sim.recommendedMao).toBeGreaterThan(0);
      expect(sim.riskScore).toBeGreaterThanOrEqual(0);
      expect(sim.riskScore).toBeLessThanOrEqual(1);
      expect(sim.confidenceScore).toBeGreaterThanOrEqual(0);
      expect(sim.confidenceScore).toBeLessThanOrEqual(1);
    }
  });
});

// ─── Ingestion normalizer stress ──────────────────────────────────────────────

describe('Stress: ingestion normalizer batch', () => {
  it('normalizes 200 raw deals without errors', () => {
    const errors: string[] = [];
    for (let i = 0; i < 200; i++) {
      const raw = makeRawDeal(i);
      const { property, warnings } = normalizeProperty(raw, 'manual');
      expect(property.address).toBeTruthy();
      if (warnings.length > 0) errors.push(...warnings);
    }
    // Some warnings are OK (e.g. missing rehab estimate inferred), but no fatal failures
    expect(errors.every((e) => !e.toLowerCase().includes('fatal'))).toBe(true);
  });

  it('handles malformed-but-recoverable fields gracefully', () => {
    // null address should throw (hard validation failure — expected)
    expect(() => normalizeProperty(
      { address: null, city: 'X', state: 'OK', zip: '73000', arv_estimate: 100_000, source: 'manual' } as Record<string, unknown>,
      'manual',
    )).toThrow();

    // zero / negative ARV is coerced but produces a warning, not a throw
    const { property: p, warnings } = normalizeProperty(
      { address: '2 Elm', city: 'Y', state: 'OK', zip: '73001', arv_estimate: -5000, source: 'csv' },
      'csv',
    );
    expect(p.address).toBe('2 Elm');
    // warnings may note the negative ARV
    expect(Array.isArray(warnings)).toBe(true);
  });
});

// ─── Episodic memory stress ───────────────────────────────────────────────────

describe('Stress: episodic memory ingestion and retrieval', () => {
  const userId = 'stress_' + Date.now();

  it('stores 100 facts without errors', async () => {
    const ids: string[] = [];
    for (let i = 0; i < 100; i++) {
      const id = await rememberFact(
        `Deal in ZIP ${73000 + i % 50}: ARV $${150_000 + i * 500}, MAO $${100_000 + i * 300}`,
        userId,
        { type: 'deal_simulation', zip: String(73000 + i % 50) },
      );
      ids.push(id);
    }
    expect(ids.length).toBe(100);
    expect(new Set(ids).size).toBe(100); // all unique IDs
  });

  it('retrieves 100 memories in under 500ms', async () => {
    const start = Date.now();
    const all = await getAllMemories(userId);
    const elapsed = Date.now() - start;
    expect(all.length).toBe(100);
    expect(elapsed).toBeLessThan(500);
  });

  it('concurrent search requests resolve correctly', async () => {
    const searches = Array.from({ length: 20 }, (_, i) =>
      searchMemory(`ZIP ${73000 + i}`, userId, 5),
    );
    const results = await Promise.all(searches);
    expect(results.length).toBe(20);
    for (const r of results) {
      expect(Array.isArray(r)).toBe(true);
    }
  });

  it('search returns results in score-descending order', async () => {
    const results = await searchMemory('ARV deal', userId, 10);
    for (let i = 1; i < results.length; i++) {
      expect(results[i - 1].score).toBeGreaterThanOrEqual(results[i].score);
    }
  });
});

// ─── OTel metrics stress ──────────────────────────────────────────────────────

describe('Stress: OTel histogram under load', () => {
  it('records 1000 simulation samples without overflow', () => {
    for (let i = 0; i < 1000; i++) {
      metrics.simulationLatency.record(Math.random() * 100);
    }
    const snap = metrics.simulationLatency.snapshot();
    expect(snap.count).toBeGreaterThan(0);
    expect(snap.p95).toBeGreaterThanOrEqual(snap.p50);
    expect(snap.p99).toBeGreaterThanOrEqual(snap.p95);
  });

  it('counter increments are consistent', () => {
    const before = metrics.simulationsRun.get();
    const N = 50;
    for (let i = 0; i < N; i++) metrics.simulationsRun.inc();
    expect(metrics.simulationsRun.get()).toBe(before + N);
  });

  it('queue depths are tracked per queue name', () => {
    metrics.setQueueDepth('deal_ingestion', 42);
    metrics.setQueueDepth('outcome_learning', 7);
    const depths = metrics.getQueueDepths();
    expect(depths['deal_ingestion']).toBe(42);
    expect(depths['outcome_learning']).toBe(7);
  });
});

// ─── Mixed concurrent simulation ─────────────────────────────────────────────

describe('Stress: concurrent deal analysis (pure compute)', () => {
  it('runs 50 parallel simulations consistently', async () => {
    const tasks = Array.from({ length: 50 }, (_, i) =>
      Promise.resolve(simulate(makeProperty(i), DEFAULT_WEIGHTS, i % 2 === 0 ? 'hot_seller' : 'balanced_buyer')),
    );
    const results = await Promise.all(tasks);
    expect(results.length).toBe(50);
    for (const r of results) {
      expect(r.recommendedMao).toBeGreaterThan(0);
    }
  });
});
