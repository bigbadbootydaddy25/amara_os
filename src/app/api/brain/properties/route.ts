import { NextRequest, NextResponse } from 'next/server';
import { PropertyRepo } from '../../../../../services/brain/src/memory/postgres/property-repo.js';

export async function GET(req: NextRequest): Promise<NextResponse> {
  const { searchParams } = new URL(req.url);
  const id    = searchParams.get('id');
  const zip   = searchParams.get('zip');
  const state = searchParams.get('state');
  const limit = parseInt(searchParams.get('limit') ?? '50', 10);

  if (id) {
    const property = await PropertyRepo.findById(id).catch(() => null);
    if (!property) return NextResponse.json({ success: false, error: 'Not found' }, { status: 404 });
    return NextResponse.json({ success: true, property });
  }

  const properties = await PropertyRepo.search({ zip: zip ?? undefined, state: state ?? undefined, limit });
  return NextResponse.json({ success: true, properties, count: properties.length });
}
