import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { persistDeal, persistCsvBatch, persistJsonBatch } from '../../../../../services/brain/src/ingestion/persistent-pipeline.js';
import type { IngestionSource, MarketRegime } from '../../../../../services/brain/src/types.js';

const SingleDealSchema = z.object({
  source: z.enum(['manual', 'csv_upload', 'json_upload', 'openclaw_scrape', 'copy_paste']).default('manual'),
  marketRegime: z.enum(['hot', 'neutral', 'cold', 'distressed']).default('neutral'),
  data: z.record(z.unknown()),
});

const BatchSchema = z.object({
  source: z.enum(['manual', 'csv_upload', 'json_upload', 'openclaw_scrape', 'copy_paste']),
  marketRegime: z.enum(['hot', 'neutral', 'cold', 'distressed']).default('neutral'),
  format: z.enum(['csv', 'json']),
  payload: z.string(),
});

export async function POST(req: NextRequest): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ success: false, error: 'Invalid JSON body' }, { status: 400 });
  }

  // Detect batch vs single
  const asBatch = BatchSchema.safeParse(body);
  if (asBatch.success) {
    const { source, marketRegime, format, payload } = asBatch.data;
    const result = format === 'csv'
      ? await persistCsvBatch(payload, source as IngestionSource, marketRegime as MarketRegime)
      : await persistJsonBatch(payload, source as IngestionSource, marketRegime as MarketRegime);
    return NextResponse.json(result, { status: 200 });
  }

  const asSingle = SingleDealSchema.safeParse(body);
  if (!asSingle.success) {
    return NextResponse.json(
      { success: false, error: 'Invalid request', details: asSingle.error.flatten() },
      { status: 400 },
    );
  }

  const { source, marketRegime, data } = asSingle.data;
  const result = await persistDeal(data, source as IngestionSource, marketRegime as MarketRegime);
  return NextResponse.json(result, { status: result.success ? 200 : 422 });
}
