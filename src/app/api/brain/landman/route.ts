import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { generateOwnershipReport, formatOwnershipReport } from '../../../../../services/brain/src/landman/engine/ownership-report.js';
import { calculateAcres, parseSTR, parseLegalDescription } from '../../../../../services/brain/src/landman/parsers/legal-description-parser.js';
import { analyzeChain } from '../../../../../services/brain/src/landman/rules/title-rules.js';
import type { TitleChain, OilGasLease, STRLocation } from '../../../../../services/brain/src/landman/types.js';

const InstrumentSchema = z.object({
  deedType:         z.string(),
  book:             z.string(),
  page:             z.string(),
  instrumentDate:   z.string(),
  grantor:          z.string(),
  grantee:          z.string(),
  interestType:     z.string(),
  interestFraction: z.string().optional(),
  reservation:      z.string().optional(),
  notes:            z.string().optional(),
});

const LeaseSchema = z.object({
  book:             z.string(),
  page:             z.string(),
  lessor:           z.string(),
  lessee:           z.string(),
  leaseDate:        z.string(),
  primaryTermYears: z.number(),
  royaltyFraction:  z.number(),
  hasPughClause:    z.boolean().default(false),
  hasDepthClause:   z.boolean().default(false),
  status:           z.enum(['in_term', 'hbp', 'expired', 'released', 'unknown']),
  hbpEvidence:      z.string().optional(),
  notes:            z.string().optional(),
});

const STRSchema = z.object({
  section:     z.number().int().min(1).max(36),
  township:    z.number().int().positive(),
  townshipDir: z.enum(['N', 'S']),
  range:       z.number().int().positive(),
  rangeDir:    z.enum(['E', 'W']),
  state:       z.string().min(2).max(2),
  county:      z.string(),
});

const OwnershipReportSchema = z.object({
  strLocation:  STRSchema,
  instruments:  z.array(InstrumentSchema),
  leases:       z.array(LeaseSchema).default([]),
  totalAcres:   z.number().optional(),
  easements:    z.array(z.string()).default([]),
  mortgages:    z.array(z.string()).default([]),
  notes:        z.string().optional(),
  format:       z.enum(['json', 'text']).default('json'),
});

const AcreageSchema = z.object({
  description: z.string(),
});

export async function POST(req: NextRequest): Promise<NextResponse> {
  const { searchParams } = new URL(req.url);
  const action = searchParams.get('action') ?? 'ownership_report';

  let body: unknown;
  try { body = await req.json(); }
  catch { return NextResponse.json({ success: false, error: 'Invalid JSON' }, { status: 400 }); }

  if (action === 'acreage') {
    const parsed = AcreageSchema.safeParse(body);
    if (!parsed.success) return NextResponse.json({ success: false, error: parsed.error.flatten() }, { status: 400 });
    const acres = calculateAcres(parsed.data.description);
    return NextResponse.json({ success: true, description: parsed.data.description, acres });
  }

  if (action === 'ownership_report') {
    const parsed = OwnershipReportSchema.safeParse(body);
    if (!parsed.success) return NextResponse.json({ success: false, error: parsed.error.flatten() }, { status: 400 });

    const { strLocation, instruments, leases, totalAcres, easements, mortgages, notes, format } = parsed.data;

    const chain: TitleChain = {
      strLocation: strLocation as STRLocation,
      instruments: instruments as TitleChain['instruments'],
      builtAt:     new Date(),
    };

    const report = generateOwnershipReport({
      chain,
      leases:      leases as OilGasLease[],
      state:       strLocation.state,
      totalAcres,
      easements,
      mortgages:   mortgages,
      notes,
    });

    if (format === 'text') {
      return new NextResponse(formatOwnershipReport(report), {
        status: 200,
        headers: { 'Content-Type': 'text/plain' },
      });
    }

    return NextResponse.json({ success: true, report });
  }

  return NextResponse.json({ success: false, error: `Unknown action: ${action}` }, { status: 400 });
}
