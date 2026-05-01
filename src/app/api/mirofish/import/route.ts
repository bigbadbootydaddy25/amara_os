import { NextRequest, NextResponse } from 'next/server';
import { importMiroFishScores } from '@/lib/mirofish/score-importer';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(_request: NextRequest) {
  try {
    const result = await importMiroFishScores();
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'MiroFish import failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
