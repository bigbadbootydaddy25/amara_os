import { NextRequest, NextResponse } from 'next/server';
import { getCurrentIQ } from '@/lib/iq/iq-engine';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(_request: NextRequest) {
  const iq = await getCurrentIQ();
  return NextResponse.json({ iq });
}
