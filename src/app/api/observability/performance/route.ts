import { NextRequest, NextResponse } from 'next/server';
import { generatePerformanceReport } from '@/lib/observability/performance-report';
import { getDailyUsageSummary } from '@/lib/observability/cost-tracker';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(_request: NextRequest) {
  const report = generatePerformanceReport();
  const usage = getDailyUsageSummary();
  return NextResponse.json({ report, usage });
}
