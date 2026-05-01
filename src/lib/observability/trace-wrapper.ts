import { getLangfuse, writeLocalTrace } from './langfuse-client';

export interface TraceContext {
  agentName: string;
  market?: string;
  input?: unknown;
}

export interface TraceResult {
  output?: unknown;
  tokenCount?: number;
  success: boolean;
  error?: string;
}

export async function withTrace<T>(
  ctx: TraceContext,
  fn: () => Promise<T>,
): Promise<T> {
  const lf = getLangfuse();
  const startTime = Date.now();
  let result: T;
  let errorMsg: string | undefined;

  const trace = lf?.trace({
    name: ctx.agentName,
    input: ctx.input,
    metadata: { market: ctx.market },
  });

  const span = trace?.span({
    name: `${ctx.agentName}_run`,
    input: ctx.input,
    startTime: new Date(startTime),
  });

  try {
    result = await fn();

    span?.end({ output: result, endTime: new Date() });
    trace?.update({ output: result });
    await lf?.flushAsync().catch(() => {});

    return result;
  } catch (err) {
    errorMsg = err instanceof Error ? err.message : String(err);

    span?.end({ output: { error: errorMsg }, level: 'ERROR', endTime: new Date() });
    trace?.update({ output: { error: errorMsg } });
    await lf?.flushAsync().catch(() => {});

    throw err;
  } finally {
    const duration = Date.now() - startTime;

    // Always write local fallback trace
    writeLocalTrace({
      agentName: ctx.agentName,
      market: ctx.market,
      input: ctx.input,
      success: !errorMsg,
      error: errorMsg,
      durationMs: duration,
      timestamp: new Date().toISOString(),
    });
  }
}
