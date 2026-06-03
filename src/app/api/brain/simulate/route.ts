import { NextRequest, NextResponse } from 'next/server';
import { z } from 'zod';
import { simulate, DEFAULT_WEIGHTS } from '../../../../../services/brain/src/mirofish/engine/simulator.js';
import { WeightsRepo } from '../../../../../services/brain/src/memory/postgres/weights-repo.js';
import { PropertyRepo } from '../../../../../services/brain/src/memory/postgres/property-repo.js';
import { SimulationRepo } from '../../../../../services/brain/src/memory/postgres/simulation-repo.js';
import type { MarketRegime } from '../../../../../services/brain/src/types.js';

const Schema = z.object({
  propertyId: z.string().uuid().optional(),
  property: z.record(z.unknown()).optional(),
  marketRegime: z.enum(['hot', 'neutral', 'cold', 'distressed']).default('neutral'),
}).refine((d) => d.propertyId ?? d.property, {
  message: 'Provide either propertyId (existing) or property (inline)',
});

export async function POST(req: NextRequest): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ success: false, error: 'Invalid JSON' }, { status: 400 });
  }

  const parsed = Schema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ success: false, error: parsed.error.flatten() }, { status: 400 });
  }

  const { propertyId, property: inlineProperty, marketRegime } = parsed.data;

  let property;
  if (propertyId) {
    property = await PropertyRepo.findById(propertyId).catch(() => null);
    if (!property) {
      return NextResponse.json({ success: false, error: 'Property not found' }, { status: 404 });
    }
  } else {
    property = inlineProperty as Parameters<typeof simulate>[0];
  }

  const weights = await WeightsRepo.getLatest().catch(() => null) ?? DEFAULT_WEIGHTS;
  const result = simulate(property, weights, marketRegime as MarketRegime);

  if (propertyId) {
    await SimulationRepo.create(result).catch((err: Error) =>
      console.warn('[simulate] failed to persist:', err.message),
    );
  }

  return NextResponse.json({ success: true, simulation: result });
}

export async function GET(req: NextRequest): Promise<NextResponse> {
  const { searchParams } = new URL(req.url);
  const propertyId = searchParams.get('propertyId');
  const dealId = searchParams.get('dealId');

  if (propertyId) {
    const sim = await SimulationRepo.findLatestForProperty(propertyId).catch(() => null);
    if (!sim) return NextResponse.json({ success: false, error: 'No simulation found' }, { status: 404 });
    return NextResponse.json({ success: true, simulation: sim });
  }

  if (dealId) {
    const sims = await SimulationRepo.findByDeal(dealId).catch(() => []);
    return NextResponse.json({ success: true, simulations: sims });
  }

  return NextResponse.json({ success: false, error: 'Provide propertyId or dealId' }, { status: 400 });
}
