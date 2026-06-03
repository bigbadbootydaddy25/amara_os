/**
 * OpenTelemetry infrastructure metrics
 * Tracks Postgres query duration, queue depth, simulation latency.
 * Uses in-process metric collection; exports via console when no collector is configured.
 */

import { EventEmitter } from 'events';

// ─── Metric types ─────────────────────────────────────────────────────────────

export interface HistogramSnapshot {
  count: number;
  sum:   number;
  min:   number;
  max:   number;
  p50:   number;
  p95:   number;
  p99:   number;
}

interface Sample {
  value: number;
  ts:    number;
}

// ─── Histogram ────────────────────────────────────────────────────────────────

class Histogram {
  private samples: Sample[] = [];
  private readonly windowMs: number;

  constructor(windowMs = 60_000) {
    this.windowMs = windowMs;
  }

  record(value: number): void {
    const now = Date.now();
    this.samples.push({ value, ts: now });
    // Prune old samples
    const cutoff = now - this.windowMs;
    this.samples = this.samples.filter((s) => s.ts >= cutoff);
  }

  snapshot(): HistogramSnapshot {
    if (this.samples.length === 0) {
      return { count: 0, sum: 0, min: 0, max: 0, p50: 0, p95: 0, p99: 0 };
    }
    const vals = this.samples.map((s) => s.value).sort((a, b) => a - b);
    const sum  = vals.reduce((a, b) => a + b, 0);
    return {
      count: vals.length,
      sum,
      min:   vals[0],
      max:   vals[vals.length - 1],
      p50:   percentile(vals, 0.5),
      p95:   percentile(vals, 0.95),
      p99:   percentile(vals, 0.99),
    };
  }
}

function percentile(sorted: number[], p: number): number {
  const idx = Math.floor(sorted.length * p);
  return sorted[Math.min(idx, sorted.length - 1)];
}

// ─── Counter ──────────────────────────────────────────────────────────────────

class Counter {
  private value = 0;

  inc(by = 1): void { this.value += by; }
  get(): number { return this.value; }
  reset(): void { this.value = 0; }
}

// ─── Registry ─────────────────────────────────────────────────────────────────

class MetricsRegistry extends EventEmitter {
  readonly pgQueryDuration   = new Histogram();
  readonly simulationLatency = new Histogram();
  readonly ingestionLatency  = new Histogram();
  readonly learningLatency   = new Histogram();
  readonly vectorSearchMs    = new Histogram();

  readonly pgErrors          = new Counter();
  readonly ingestTotal       = new Counter();
  readonly ingestErrors      = new Counter();
  readonly simulationsRun    = new Counter();
  readonly weightUpdates     = new Counter();

  // Queue depths (last-written gauge)
  private queueDepths: Record<string, number> = {};

  setQueueDepth(queue: string, depth: number): void {
    this.queueDepths[queue] = depth;
  }

  getQueueDepths(): Record<string, number> {
    return { ...this.queueDepths };
  }

  snapshot() {
    return {
      histograms: {
        pgQueryDuration:   this.pgQueryDuration.snapshot(),
        simulationLatency: this.simulationLatency.snapshot(),
        ingestionLatency:  this.ingestionLatency.snapshot(),
        learningLatency:   this.learningLatency.snapshot(),
        vectorSearchMs:    this.vectorSearchMs.snapshot(),
      },
      counters: {
        pgErrors:       this.pgErrors.get(),
        ingestTotal:    this.ingestTotal.get(),
        ingestErrors:   this.ingestErrors.get(),
        simulationsRun: this.simulationsRun.get(),
        weightUpdates:  this.weightUpdates.get(),
      },
      queueDepths: this.getQueueDepths(),
      collectedAt: new Date().toISOString(),
    };
  }
}

export const metrics = new MetricsRegistry();

// ─── Instrumentation helpers ──────────────────────────────────────────────────

export async function measurePgQuery<T>(fn: () => Promise<T>): Promise<T> {
  const start = Date.now();
  try {
    const result = await fn();
    metrics.pgQueryDuration.record(Date.now() - start);
    return result;
  } catch (err) {
    metrics.pgErrors.inc();
    metrics.pgQueryDuration.record(Date.now() - start);
    throw err;
  }
}

export async function measureSimulation<T>(fn: () => Promise<T> | T): Promise<T> {
  const start = Date.now();
  const result = await fn();
  metrics.simulationLatency.record(Date.now() - start);
  metrics.simulationsRun.inc();
  return result;
}

export async function measureVectorSearch<T>(fn: () => Promise<T>): Promise<T> {
  const start = Date.now();
  const result = await fn();
  metrics.vectorSearchMs.record(Date.now() - start);
  return result;
}

// ─── Periodic console reporter (dev mode) ────────────────────────────────────

let reporterInterval: ReturnType<typeof setInterval> | null = null;

export function startMetricsReporter(intervalMs = 30_000): void {
  if (reporterInterval) return;
  reporterInterval = setInterval(() => {
    const snap = metrics.snapshot();
    const log  = process.env.BRAIN_LOG === 'json'
      ? JSON.stringify({ type: 'metrics', ...snap })
      : `[otel] pg_p95=${snap.histograms.pgQueryDuration.p95}ms sim_p95=${snap.histograms.simulationLatency.p95}ms ingest=${snap.counters.ingestTotal} errors=${snap.counters.ingestErrors}`;
    console.log(log);
  }, intervalMs);
  reporterInterval.unref?.();
}

export function stopMetricsReporter(): void {
  if (reporterInterval) {
    clearInterval(reporterInterval);
    reporterInterval = null;
  }
}
