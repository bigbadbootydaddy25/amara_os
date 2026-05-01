import { NextRequest, NextResponse } from 'next/server';
import { runSelfImprovementCycle } from '@/lib/self-improvement/self-improvement-loop';
import { watchAndIngest } from '@/lib/knowledge/notebooklm-watcher';
import { syncLlmWiki } from '@/lib/knowledge/llm-wiki-sync';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const maxDuration = 300;

export async function POST(_request: NextRequest) {
  try {
    const [cycleResult, knowledgeResult, wikiResult] = await Promise.all([
      runSelfImprovementCycle(),
      watchAndIngest(),
      syncLlmWiki(),
    ]);

    return NextResponse.json({ cycleResult, knowledgeResult, wikiResult });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Self-improvement cycle failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
