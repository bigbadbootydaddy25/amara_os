import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { parseOpenClawPayload } from '../../../../../services/brain/src/ingestion/parsers/openclaw-parser.js';
import { persistDeal } from '../../../../../services/brain/src/ingestion/persistent-pipeline.js';
import { normalizeProperty } from '../../../../../services/brain/src/ingestion/normalizers/property-normalizer.js';

// ─── Schema ───────────────────────────────────────────────────────────────────

const OpenClawSchema = z.object({
  format:       z.enum(['json', 'html']),
  data:         z.union([z.record(z.unknown()), z.string()]),
  source:       z.string().optional(),   // e.g. "payne_county_ok"
  persist:      z.boolean().default(true),
  marketRegime: z.enum(['hot', 'neutral', 'cold', 'distressed']).default('neutral'),
});

// ─── Handler ──────────────────────────────────────────────────────────────────

export async function POST(req: NextRequest): Promise<NextResponse> {
  let body: unknown;
  try { body = await req.json(); }
  catch { return NextResponse.json({ success: false, error: 'Invalid JSON' }, { status: 400 }); }

  const parsed = OpenClawSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ success: false, error: parsed.error.flatten() }, { status: 400 });
  }

  const { format, data, source, persist, marketRegime } = parsed.data;

  // Parse OpenClaw payload into canonical field map
  const { fields, warnings: parseWarnings } = parseOpenClawPayload({
    format,
    data: data as Record<string, unknown> | string,
    source,
  });

  if (!persist) {
    // Preview mode — just return normalized fields without persisting
    try {
      const { property, warnings: normWarnings } = normalizeProperty(fields, 'openclaw_scrape');
      return NextResponse.json({
        success: true,
        preview: true,
        property,
        parseWarnings,
        normWarnings,
      });
    } catch (err) {
      return NextResponse.json({
        success: false,
        error: err instanceof Error ? err.message : String(err),
        parseWarnings,
        fields,
      }, { status: 422 });
    }
  }

  // Persist mode — full ingest + simulation
  const result = await persistDeal(fields, 'openclaw_scrape', marketRegime);

  return NextResponse.json({
    success: result.success,
    propertyId:   result.propertyId,
    simulationId: result.simulationId,
    parseWarnings,
    errors: result.errors,
    processingMs: result.processingMs,
  }, { status: result.success ? 200 : 422 });
}
