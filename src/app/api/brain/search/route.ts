import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import {
  searchProperties,
  searchMarketIntel,
  searchBuyers,
} from '../../../../../services/brain/src/memory/qdrant/vector-store.js';
import { traceRetrieval } from '../../../../../services/brain/src/observability/tracer.js';

const Schema = z.object({
  query:      z.string().min(3, 'Query too short'),
  collection: z.enum(['properties', 'market_intel', 'buyers']).default('properties'),
  zip:        z.string().regex(/^\d{5}/).optional(),
  state:      z.string().length(2).optional(),
  regime:     z.enum(['hot', 'neutral', 'cold', 'distressed']).optional(),
  buyerType:  z.string().optional(),
  maxRisk:    z.number().min(0).max(1).optional(),
  minArv:     z.number().positive().optional(),
  limit:      z.number().int().min(1).max(50).default(10),
});

export async function POST(req: NextRequest): Promise<NextResponse> {
  let body: unknown;
  try { body = await req.json(); }
  catch { return NextResponse.json({ success: false, error: 'Invalid JSON' }, { status: 400 }); }

  const parsed = Schema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ success: false, error: parsed.error.flatten() }, { status: 400 });
  }

  const { query, collection, zip, state, regime, buyerType, maxRisk, minArv, limit } = parsed.data;

  try {
    if (collection === 'properties') {
      const results = await traceRetrieval(query, 'properties', () =>
        searchProperties(query, { zip, state, maxRisk, minArv }, limit),
      );
      return NextResponse.json({ success: true, collection, results });
    }

    if (collection === 'market_intel') {
      const results = await traceRetrieval(query, 'market_intel', () =>
        searchMarketIntel(query, { zip, regime }, limit),
      );
      return NextResponse.json({ success: true, collection, results });
    }

    if (collection === 'buyers') {
      const results = await traceRetrieval(query, 'buyers', () =>
        searchBuyers(query, { zip, buyerType }, limit),
      );
      return NextResponse.json({ success: true, collection, results });
    }

    return NextResponse.json({ success: false, error: 'Unknown collection' }, { status: 400 });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}
