import { NextRequest, NextResponse } from 'next/server';
import { runMorningRoutine } from '@/lib/openclaw/morning-routine';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const maxDuration = 300;

export async function POST(_request: NextRequest) {
  try {
    const result = await runMorningRoutine();
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Morning routine failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
