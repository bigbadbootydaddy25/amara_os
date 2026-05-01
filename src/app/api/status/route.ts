import { NextRequest, NextResponse } from 'next/server';
import { verifyConnectivity, runQuery } from '@/lib/neural-graph/neo4j-client';
import { getMemoryClient } from '@/lib/memory/mem0-client';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

async function checkOllama(): Promise<{ ok: boolean; model: string | null }> {
  const base = process.env.OLLAMA_BASE_URL?.trim() || 'http://localhost:11434';
  try {
    const res = await fetch(`${base}/api/tags`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) return { ok: false, model: null };
    const model = process.env.OLLAMA_MODEL?.trim() || 'llama3';
    return { ok: true, model };
  } catch {
    return { ok: false, model: null };
  }
}

async function checkNeo4j(): Promise<{ ok: boolean; counts: Record<string, number> | null }> {
  try {
    await verifyConnectivity();
    const rows = await runQuery<{ label: string; count: { low: number } }>(
      `CALL apoc.meta.stats() YIELD labels
       UNWIND keys(labels) AS label
       RETURN label, labels[label] AS count`,
    ).catch(async () => {
      // apoc may not be installed — fallback to basic counts
      const buyers = await runQuery<{ n: { low: number } }>('MATCH (b:Buyer) RETURN count(b) AS n');
      const deals = await runQuery<{ n: { low: number } }>('MATCH (d:Deal) RETURN count(d) AS n');
      const matches = await runQuery<{ n: { low: number } }>('MATCH ()-[r:LIKELY_TO_BUY]->() RETURN count(r) AS n');
      const signals = await runQuery<{ n: { low: number } }>('MATCH (s:Signal) RETURN count(s) AS n');
      return [
        { label: 'Buyer', count: buyers[0]?.n ?? { low: 0 } },
        { label: 'Deal', count: deals[0]?.n ?? { low: 0 } },
        { label: 'LIKELY_TO_BUY', count: matches[0]?.n ?? { low: 0 } },
        { label: 'Signal', count: signals[0]?.n ?? { low: 0 } },
      ];
    });

    const counts: Record<string, number> = {};
    for (const row of rows) {
      counts[row.label] = row.count?.low ?? 0;
    }
    return { ok: true, counts };
  } catch {
    return { ok: false, counts: null };
  }
}

export async function GET(_request: NextRequest) {
  const [ollamaStatus, neo4jStatus] = await Promise.all([checkOllama(), checkNeo4j()]);

  const anthropicConfigured = Boolean(process.env.ANTHROPIC_API_KEY?.trim());
  const mem0Configured = Boolean(getMemoryClient());
  const langfuseConfigured = Boolean(process.env.LANGFUSE_PUBLIC_KEY?.trim());
  const elevenLabsConfigured = Boolean(process.env.ELEVENLABS_API_KEY?.trim());

  const allCriticalOk = ollamaStatus.ok || anthropicConfigured;

  return NextResponse.json(
    {
      status: allCriticalOk ? 'OPERATIONAL' : 'DEGRADED',
      timestamp: new Date().toISOString(),
      backends: {
        ollama: { ...ollamaStatus, configured: true },
        claude: { ok: anthropicConfigured, configured: anthropicConfigured },
        mem0: { ok: mem0Configured, configured: mem0Configured },
        langfuse: { ok: langfuseConfigured, configured: langfuseConfigured },
        elevenlabs: { ok: elevenLabsConfigured, configured: elevenLabsConfigured },
      },
      neo4j: neo4jStatus,
      endpoints: {
        chat:             'POST /api/chat',
        ingest:           'POST /api/neural-graph/ingest',
        hermes:           'POST /api/hermes/run',
        pipeline:         'POST /api/pipeline/run',
        briefing:         'POST /api/briefing',
        mirofish_import:  'POST /api/mirofish/import',
        kill_shots:       'GET  /api/mirofish/kill-shots',
        morning_routine:  'POST /api/openclaw/morning-routine',
        self_improve:     'POST /api/self-improvement/run',
        iq_events:        'GET  /api/iq/events  (SSE)',
        iq_current:       'GET  /api/iq/current',
        performance:      'GET  /api/observability/performance',
        status:           'GET  /api/status',
      },
    },
    { status: allCriticalOk ? 200 : 503 },
  );
}
