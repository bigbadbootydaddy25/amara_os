import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { runAcquisitionScoutAgent } from '../../../../../services/brain/src/agents/graphs/acquisition-scout-graph.js';
import { runDispositionMatcherAgent } from '../../../../../services/brain/src/agents/graphs/disposition-matcher-graph.js';
import { runDealNegotiatorAgent } from '../../../../../services/brain/src/agents/graphs/deal-negotiator-graph.js';

// ─── Schemas ──────────────────────────────────────────────────────────────────

const PropertySchema = z.object({
  id:            z.string().optional(),
  address:       z.string(),
  city:          z.string(),
  state:         z.string(),
  zip:           z.string(),
  county:        z.string().optional(),
  apn:           z.string().optional(),
  beds:          z.number().optional(),
  baths:         z.number().optional(),
  sqft:          z.number().optional(),
  yearBuilt:     z.number().optional(),
  condition:     z.string().optional(),
  arvEstimate:   z.number().optional(),
  listPrice:     z.number().optional(),
  rehabEstimate: z.number().optional(),
  taxDelinquent: z.boolean().optional(),
  vacant:        z.boolean().optional(),
  preForeclosure:z.boolean().optional(),
});

const ScoutSchema = z.object({
  agent:        z.literal('scout'),
  property:     PropertySchema,
  marketRegime: z.enum(['hot', 'neutral', 'cold', 'distressed']).optional(),
});

const MatcherSchema = z.object({
  agent:      z.literal('matcher'),
  propertyId: z.string(),
  zip:        z.string(),
  mao:        z.number().optional(),
  arv:        z.number().optional(),
  strategy:   z.string().optional(),
});

const NegotiatorSchema = z.object({
  agent:        z.literal('negotiator'),
  property:     PropertySchema,
  currentOffer: z.number(),
  sellerAsk:    z.number(),
  marketRegime: z.enum(['hot', 'neutral', 'cold', 'distressed']).optional(),
});

const HermesSchema = z.discriminatedUnion('agent', [
  ScoutSchema,
  MatcherSchema,
  NegotiatorSchema,
]);

// ─── Handler ──────────────────────────────────────────────────────────────────

export async function POST(req: NextRequest): Promise<NextResponse> {
  let body: unknown;
  try { body = await req.json(); }
  catch { return NextResponse.json({ success: false, error: 'Invalid JSON' }, { status: 400 }); }

  const parsed = HermesSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ success: false, error: parsed.error.flatten() }, { status: 400 });
  }

  const input = parsed.data;

  try {
    if (input.agent === 'scout') {
      const result = await runAcquisitionScoutAgent({
        ...input.property,
        ingestionSource: 'manual',
      });
      return NextResponse.json({ success: true, agent: 'scout', result });
    }

    if (input.agent === 'matcher') {
      const result = await runDispositionMatcherAgent(input);
      return NextResponse.json({ success: true, agent: 'matcher', result });
    }

    if (input.agent === 'negotiator') {
      const result = await runDealNegotiatorAgent({
        ...input,
        property: { ...input.property, ingestionSource: 'manual' },
      });
      return NextResponse.json({ success: true, agent: 'negotiator', result });
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }

  return NextResponse.json({ success: false, error: 'Unknown agent' }, { status: 400 });
}
