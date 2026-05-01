import { NextRequest, NextResponse } from 'next/server';
import { findKillShots, writeKillShotReport } from '@/lib/mirofish/kill-shot-finder';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const threshold = parseFloat(searchParams.get('threshold') ?? '0.8');
    const deals = await findKillShots(threshold);
    const report = writeKillShotReport(deals);
    return NextResponse.json({ deals, report });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Kill shot query failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
