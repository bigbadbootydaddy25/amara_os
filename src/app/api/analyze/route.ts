import { NextRequest, NextResponse } from 'next/server';
import { getPropertyById, getBuyers, upsertProperty } from '@/lib/data-store';
import { classifyDeal } from '@/lib/deal-classifier';
import { analyzeDeal } from '@/lib/deal-analyzer';
import { findBestMatches } from '@/lib/exit-matcher';
import { generateOffer } from '@/lib/offer-engine';
import { linkPropertyToBuyer, isNeo4jAvailable } from '@/lib/neo4j-client';
import type { TopDealSummary } from '@/types/real-estate';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as {
      propertyId?: string;
      params?: Record<string, number | string>;
    };

    const property = body.propertyId ? getPropertyById(body.propertyId) : null;
    if (!property) {
      return NextResponse.json({ error: 'Property not found' }, { status: 404 });
    }

    const params = body.params ?? {};

    // Classify deal type
    const dealType = classifyDeal({
      deadPaperScore: property.deadPaperScore,
      deadPaperFlags: property.deadPaperFlags,
      osint: property.osint,
      parcelAcres: Number(params.parcelAcres ?? 0),
      hasRentalIncome: Boolean(params.hasRentalIncome),
      estimatedRepairs: Number(params.repairEstimate ?? 0),
      arv: Number(params.arv ?? 0),
    });

    // Analyze deal financials
    const analysis = analyzeDeal(dealType, params);

    // Match to buyers
    const buyers = getBuyers();
    const updatedProperty = { ...property, dealType, analysis };
    const exitMatches = findBestMatches(updatedProperty, buyers);
    const exitMatch = exitMatches[0] ?? undefined;

    // Generate offer
    const offerTerms = generateOffer(dealType, analysis);

    // Persist
    const finalProperty = {
      ...updatedProperty,
      exitMatch,
      offerTerms,
      dealStatus: 'offer_ready' as const,
      updatedAt: new Date().toISOString(),
    };
    upsertProperty(finalProperty);

    // Sync to Neo4j if available
    if (exitMatch && (await isNeo4jAvailable())) {
      await linkPropertyToBuyer(
        property.id,
        exitMatch.buyerId,
        exitMatch.confidenceScore,
      ).catch(() => null);
    }

    const spread = analysis.spread ?? 0;
    const arvOrValue = analysis.arv ?? analysis.totalProjectedRevenue ?? property.listingPrice ?? 0;
    const cost = analysis.mao ?? analysis.acquisitionCost ?? 0;

    const summary: TopDealSummary = {
      property: finalProperty,
      type: dealType,
      score: property.deadPaperScore,
      arvOrValue,
      cost,
      spread,
      exitBuyer: exitMatch?.buyerName,
      strategy: analysis.dealType,
    };

    return NextResponse.json({ analysis, exitMatches, offerTerms, summary });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Analysis failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

// GET top deals across all properties
export async function GET() {
  const { getProperties } = await import('@/lib/data-store');
  const buyers = getBuyers();
  const properties = getProperties();

  const topDeals: TopDealSummary[] = properties
    .filter((p) => p.analysis && p.dealType)
    .map((p) => {
      const spread = p.analysis!.spread ?? 0;
      const arvOrValue =
        p.analysis!.arv ?? p.analysis!.totalProjectedRevenue ?? p.listingPrice ?? 0;
      const cost = p.analysis!.mao ?? p.analysis!.acquisitionCost ?? 0;
      const exits = findBestMatches(p, buyers, 1);
      return {
        property: p,
        type: p.dealType!,
        score: p.deadPaperScore,
        arvOrValue,
        cost,
        spread,
        exitBuyer: exits[0]?.buyerName,
        strategy: p.dealType!,
      } satisfies TopDealSummary;
    })
    .sort((a, b) => b.spread - a.spread)
    .slice(0, 10);

  return NextResponse.json({ topDeals });
}
