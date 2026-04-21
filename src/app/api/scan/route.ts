import { NextRequest, NextResponse } from 'next/server';
import { getProperties, getBuyers, upsertProperty } from '@/lib/data-store';
import { classifyDeal } from '@/lib/deal-classifier';
import { analyzeDeal } from '@/lib/deal-analyzer';
import { findBestMatches } from '@/lib/exit-matcher';
import { generateOffer } from '@/lib/offer-engine';
import type { AutomationState, Property } from '@/types/real-estate';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// In-memory automation state (persists for the process lifetime)
let automationState: AutomationState = {
  isRunning: false,
  log: [],
};

function log(msg: string) {
  const entry = `[${new Date().toISOString()}] ${msg}`;
  automationState.log = [entry, ...automationState.log].slice(0, 100);
}

async function runAutomationCycle(): Promise<number> {
  log('Scan cycle started');
  automationState.currentStep = 'Scoring unanalyzed properties';

  const properties = getProperties();
  const buyers = getBuyers();
  let processed = 0;

  const unanalyzed = properties.filter((p) => !p.analysis && p.dealStatus === 'new');

  for (const property of unanalyzed) {
    automationState.currentStep = `Analyzing ${property.address}`;
    log(`Analyzing: ${property.address}`);

    try {
      const dealType = classifyDeal({
        deadPaperScore: property.deadPaperScore,
        deadPaperFlags: property.deadPaperFlags,
        osint: property.osint,
      });

      // Use listing price as base if no ARV provided
      const price = property.listingPrice ?? 0;
      const params: Record<string, number | string> = {
        arv: price * 1.2,
        repairEstimate: price * 0.1,
        acquisitionCost: price,
        lotYield: 10,
        builderResalePerLot: price / 8,
        infrastructureCostEstimate: price * 0.15,
        monthlyRent: price * 0.008,
      };

      const analysis = analyzeDeal(dealType, params);
      const updatedProperty: Property = { ...property, dealType, analysis };
      const exits = findBestMatches(updatedProperty, buyers);
      const offerTerms = generateOffer(dealType, analysis);

      upsertProperty({
        ...updatedProperty,
        exitMatch: exits[0],
        offerTerms,
        dealStatus: 'offer_ready',
        updatedAt: new Date().toISOString(),
      });

      log(`✓ ${property.address} → ${dealType} | spread $${(analysis.spread ?? 0).toLocaleString()}`);
      processed++;
    } catch (err) {
      log(`✗ ${property.address}: ${err instanceof Error ? err.message : 'error'}`);
    }
  }

  automationState.currentStep = undefined;
  automationState.lastScanAt = new Date().toISOString();
  log(`Scan cycle complete — ${processed} properties processed`);
  return processed;
}

export async function POST(request: NextRequest) {
  const body = (await request.json().catch(() => ({}))) as { action?: string };

  if (body.action === 'status') {
    return NextResponse.json({ state: automationState });
  }

  if (automationState.isRunning) {
    return NextResponse.json({ error: 'Scan already running' }, { status: 409 });
  }

  automationState.isRunning = true;
  log('Automation loop triggered');

  runAutomationCycle()
    .then((n) => {
      log(`Loop complete: ${n} deals processed`);
    })
    .catch((err) => {
      log(`Loop error: ${err instanceof Error ? err.message : 'unknown'}`);
    })
    .finally(() => {
      automationState.isRunning = false;
    });

  return NextResponse.json({ ok: true, message: 'Scan started' });
}

export async function GET() {
  return NextResponse.json({ state: automationState });
}
