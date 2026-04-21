import { NextRequest, NextResponse } from 'next/server';
import { getProperties, upsertProperty, deleteProperty } from '@/lib/data-store';
import { syncPropertyToGraph, isNeo4jAvailable } from '@/lib/neo4j-client';
import { detectFlags, scoreKeywords, calcDeadPaperScore } from '@/lib/dead-paper-scorer';
import type { Property } from '@/types/real-estate';
import { randomUUID } from 'crypto';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const status = searchParams.get('status');
  const zip = searchParams.get('zip');
  const dealType = searchParams.get('dealType');

  let properties = getProperties();

  if (status) properties = properties.filter((p) => p.dealStatus === status);
  if (zip) properties = properties.filter((p) => p.zip === zip);
  if (dealType) properties = properties.filter((p) => p.dealType === dealType);

  properties = properties.sort((a, b) => b.deadPaperScore - a.deadPaperScore);

  return NextResponse.json({ properties, total: properties.length });
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as Partial<Property> & {
      description?: string;
      nearbyListingCount?: number;
      parcelAcres?: number;
      nearRooftops?: boolean;
      inBuilderZone?: boolean;
    };

    if (!body.address || !body.zip) {
      return NextResponse.json({ error: 'Missing required fields: address, zip' }, { status: 400 });
    }

    const description = body.description ?? '';
    const keywordScore = scoreKeywords(description);
    const flags = detectFlags(body.address, description, {
      nearbyListingCount: body.nearbyListingCount,
      parcelAcres: body.parcelAcres,
      nearRooftops: body.nearRooftops,
      inBuilderZone: body.inBuilderZone,
    });
    const deadPaperScore = calcDeadPaperScore(flags, keywordScore);

    const property: Property = {
      id: body.id ?? randomUUID(),
      address: body.address,
      city: body.city ?? '',
      state: body.state ?? '',
      zip: body.zip,
      apn: body.apn,
      listingPrice: body.listingPrice,
      listingSource: body.listingSource ?? 'manual',
      listingUrl: body.listingUrl,
      listingKeywords: body.listingKeywords ?? [],
      deadPaperScore,
      deadPaperFlags: flags,
      dealType: body.dealType,
      dealStatus: body.dealStatus ?? 'new',
      osint: body.osint ?? { status: 'pending' },
      analysis: body.analysis,
      exitMatch: body.exitMatch,
      offerTerms: body.offerTerms,
      notes: body.notes,
      createdAt: body.createdAt ?? new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    upsertProperty(property);

    if (await isNeo4jAvailable()) {
      await syncPropertyToGraph(property).catch(() => null);
    }

    return NextResponse.json({ property }, { status: 201 });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to save property';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function DELETE(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const id = searchParams.get('id');
  if (!id) return NextResponse.json({ error: 'Missing id' }, { status: 400 });
  deleteProperty(id);
  return NextResponse.json({ ok: true });
}
