import { NextRequest, NextResponse } from 'next/server';
import { runHermes } from '@/lib/hermes/hermes-orchestrator';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
// Hermes runs can take a while across 37 markets
export const maxDuration = 300;

export async function POST(_request: NextRequest) {
  try {
    const result = await runHermes();
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Hermes run failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
