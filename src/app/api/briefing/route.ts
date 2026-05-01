import { NextRequest, NextResponse } from 'next/server';
import { generateMorningBriefing } from '@/lib/memory/morning-briefing';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';
export const maxDuration = 120;

export async function POST(_request: NextRequest) {
  try {
    const result = await generateMorningBriefing();
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Briefing generation failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
