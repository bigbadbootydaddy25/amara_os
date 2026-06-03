/**
 * Langfuse observability wrapper for AMARA OS.
 *
 * Traces every ingestion, simulation, learning, and retrieval call.
 * Falls back to a no-op tracer when LANGFUSE_SECRET_KEY is not set,
 * so the system runs fully offline without any external dependency.
 */

export interface TraceContext {
  traceId: string;
  name: string;
  startedAt: Date;
  metadata?: Record<string, unknown>;
}

export interface SpanResult {
  durationMs: number;
  output?: unknown;
  error?: string;
}

// ─── Langfuse SDK (optional) ─────────────────────────────────────────────────

let langfuse: LangfuseClient | null = null;

interface LangfuseClient {
  trace(params: { id: string; name: string; metadata?: unknown }): LangfuseTrace;
  flushAsync(): Promise<void>;
}

interface LangfuseTrace {
  span(params: { name: string; input?: unknown; metadata?: unknown }): LangfuseSpan;
  update(params: { output?: unknown; metadata?: unknown }): void;
}

interface LangfuseSpan {
  end(params?: { output?: unknown; level?: string; statusMessage?: string }): void;
}

async function getLangfuse(): Promise<LangfuseClient | null> {
  if (!process.env.LANGFUSE_SECRET_KEY) return null;
  if (langfuse) return langfuse;

  try {
    const { Langfuse } = await import('langfuse');
    langfuse = new Langfuse({
      secretKey:  process.env.LANGFUSE_SECRET_KEY,
      publicKey:  process.env.LANGFUSE_PUBLIC_KEY ?? '',
      baseUrl:    process.env.LANGFUSE_BASE_URL ?? 'https://cloud.langfuse.com',
    }) as unknown as LangfuseClient;
    return langfuse;
  } catch {
    return null;
  }
}

// ─── No-op fallback ──────────────────────────────────────────────────────────

const noop = {
  span: () => ({ end: () => undefined }),
  update: () => undefined,
};

// ─── Local structured logging ─────────────────────────────────────────────────

function logLocal(level: 'info' | 'warn' | 'error', event: string, data?: unknown): void {
  if (process.env.BRAIN_LOG === 'false') return;
  const ts = new Date().toISOString();
  console.log(JSON.stringify({ ts, level, event, data }));
}

// ─── Public API ──────────────────────────────────────────────────────────────

export class Tracer {
  private trace: LangfuseTrace = noop;
  private ctx: TraceContext;

  private constructor(ctx: TraceContext) {
    this.ctx = ctx;
  }

  static async start(name: string, metadata?: Record<string, unknown>): Promise<Tracer> {
    const ctx: TraceContext = {
      traceId:   crypto.randomUUID(),
      name,
      startedAt: new Date(),
      metadata,
    };

    const t = new Tracer(ctx);
    const lf = await getLangfuse();
    if (lf) {
      t.trace = lf.trace({ id: ctx.traceId, name, metadata });
    }

    logLocal('info', `trace.start:${name}`, { traceId: ctx.traceId, ...metadata });
    return t;
  }

  async span<T>(
    name: string,
    fn: () => Promise<T>,
    input?: unknown,
  ): Promise<T> {
    const span = this.trace.span({ name, input });
    const start = Date.now();

    try {
      const result = await fn();
      const durationMs = Date.now() - start;
      span.end({ output: summarize(result) });
      logLocal('info', `span.end:${name}`, { durationMs, traceId: this.ctx.traceId });
      return result;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      span.end({ level: 'ERROR', statusMessage: msg });
      logLocal('error', `span.error:${name}`, { error: msg, traceId: this.ctx.traceId });
      throw err;
    }
  }

  end(output?: unknown): void {
    const durationMs = Date.now() - this.ctx.startedAt.getTime();
    this.trace.update({ output: summarize(output) });
    logLocal('info', `trace.end:${this.ctx.name}`, { durationMs, traceId: this.ctx.traceId });
  }

  get id(): string { return this.ctx.traceId; }
}

// ─── Convenience wrappers ────────────────────────────────────────────────────

export async function traceIngestion<T>(
  source: string,
  fn: () => Promise<T>,
): Promise<T> {
  const t = await Tracer.start('ingestion', { source });
  try {
    const result = await t.span('pipeline.run', fn, { source });
    t.end(result);
    return result;
  } catch (err) {
    t.end({ error: String(err) });
    throw err;
  }
}

export async function traceSimulation<T>(
  propertyId: string,
  fn: () => Promise<T>,
): Promise<T> {
  const t = await Tracer.start('simulation', { propertyId });
  try {
    const result = await t.span('mirofish.simulate', fn, { propertyId });
    t.end(result);
    return result;
  } catch (err) {
    t.end({ error: String(err) });
    throw err;
  }
}

export async function traceLearning<T>(
  dealId: string,
  fn: () => Promise<T>,
): Promise<T> {
  const t = await Tracer.start('learning', { dealId });
  try {
    const result = await t.span('mirofish.weight_update', fn, { dealId });
    t.end(result);
    return result;
  } catch (err) {
    t.end({ error: String(err) });
    throw err;
  }
}

export async function traceRetrieval<T>(
  query: string,
  collection: string,
  fn: () => Promise<T>,
): Promise<T> {
  const t = await Tracer.start('retrieval', { query: query.slice(0, 80), collection });
  try {
    const result = await t.span('qdrant.search', fn, { query, collection });
    t.end(result);
    return result;
  } catch (err) {
    t.end({ error: String(err) });
    throw err;
  }
}

// Trim large objects to avoid bloating traces
function summarize(val: unknown): unknown {
  if (val === null || val === undefined) return val;
  if (typeof val !== 'object') return val;
  const str = JSON.stringify(val);
  if (str.length <= 2_000) return val;
  return { _truncated: true, preview: str.slice(0, 500) };
}
