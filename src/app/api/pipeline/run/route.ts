import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { dailyPipelineChain } from '@/lib/pipeline/daily-pipeline-chain';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const maxDuration = 300;

function loadMarketNames(): string[] {
  const dir = path.resolve(process.cwd(), 'data/MARKETS');
  if (!fs.existsSync(dir)) return [];

  const names: string[] = [];
  for (const file of fs.readdirSync(dir).filter((f) => f.endsWith('.json'))) {
    try {
      const raw = JSON.parse(fs.readFileSync(path.join(dir, file), 'utf-8')) as unknown;
      const markets = Array.isArray(raw) ? raw : [raw];
      for (const m of markets) {
        if (typeof m === 'object' && m !== null && 'name' in m) {
          names.push(String((m as { name: string }).name));
        }
      }
    } catch {
      // skip malformed files
    }
  }
  return names;
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json().catch(() => ({}))) as { markets?: string[]; skipBriefing?: boolean };
    const markets = (body.markets?.length ? body.markets : loadMarketNames());

    if (markets.length === 0) {
      return NextResponse.json(
        { error: 'No markets configured. Add JSON files to data/MARKETS/ or pass markets[] in body.' },
        { status: 400 },
      );
    }

    const result = await dailyPipelineChain.invoke({ markets, skipBriefing: body.skipBriefing ?? false });
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Pipeline run failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
