import { NextRequest, NextResponse } from 'next/server';
import { getBuyers, upsertBuyer, deleteBuyer } from '@/lib/data-store';
import { syncBuyerToGraph } from '@/lib/neo4j-client';
import { isNeo4jAvailable } from '@/lib/neo4j-client';
import type { Buyer } from '@/types/real-estate';
import { randomUUID } from 'crypto';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET() {
  const buyers = getBuyers();
  return NextResponse.json({ buyers, total: buyers.length });
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as Partial<Buyer>;

    if (!body.name || !body.type || !body.buyBox || !body.activeZips) {
      return NextResponse.json(
        { error: 'Missing required fields: name, type, buyBox, activeZips' },
        { status: 400 },
      );
    }

    const buyer: Buyer = {
      id: body.id ?? randomUUID(),
      name: body.name,
      llcName: body.llcName,
      email: body.email,
      phone: body.phone,
      type: body.type,
      buyBox: body.buyBox,
      activeZips: body.activeZips,
      purchases24mo: body.purchases24mo ?? 0,
      purchases36mo: body.purchases36mo ?? 0,
      strategy: body.strategy ?? '',
      notes: body.notes,
      confidenceScore: body.confidenceScore ?? 5,
      createdAt: body.createdAt ?? new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    upsertBuyer(buyer);

    if (await isNeo4jAvailable()) {
      await syncBuyerToGraph(buyer).catch(() => null);
    }

    return NextResponse.json({ buyer }, { status: 201 });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to save buyer';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function DELETE(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const id = searchParams.get('id');
  if (!id) return NextResponse.json({ error: 'Missing id' }, { status: 400 });
  deleteBuyer(id);
  return NextResponse.json({ ok: true });
}
