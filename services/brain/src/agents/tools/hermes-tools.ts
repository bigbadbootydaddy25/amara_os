/**
 * Hermes Agent Tools
 *
 * Deterministic domain tools used by the three Hermes agent graphs:
 *   - Acquisition Scout  (deal verdict from address/APN)
 *   - Disposition Matcher (best buyers for a deal)
 *   - Deal Negotiator    (counter-offer modelling)
 */

import { simulate, DEFAULT_WEIGHTS } from '../../mirofish/engine/simulator.js';
import { WeightsRepo } from '../../memory/postgres/weights-repo.js';
import { PropertyRepo } from '../../memory/postgres/property-repo.js';
import { SimulationRepo } from '../../memory/postgres/simulation-repo.js';
import { searchBuyers, searchProperties } from '../../memory/qdrant/vector-store.js';
import { findBuyersForZip } from '../../memory/neo4j/graph-sync.js';
import { recallDealsInZip, recallMarketContext } from '../../memory/mem0/episodic-memory.js';
import type { Property, SimulationResult, MarketRegime } from '../../types.js';

// ─── Acquisition Scout tools ──────────────────────────────────────────────────

export interface ScoutInput {
  property: Property;
  marketRegime?: MarketRegime;
}

export interface ScoutOutput {
  simulation:    SimulationResult;
  verdict:       'green' | 'yellow' | 'red';
  verdictReason: string;
  priorDeals:    Awaited<ReturnType<typeof recallDealsInZip>>;
  marketContext: Awaited<ReturnType<typeof recallMarketContext>>;
}

export async function runAcquisitionScout(input: ScoutInput): Promise<ScoutOutput> {
  const weights = await WeightsRepo.getLatest().catch(() => null) ?? DEFAULT_WEIGHTS;
  const simulation = simulate(input.property, weights, input.marketRegime ?? 'neutral');

  const [priorDeals, marketContext] = await Promise.all([
    recallDealsInZip(input.property.zip ?? '').catch(() => []),
    recallMarketContext(input.property.zip ?? '').catch(() => []),
  ]);

  const { riskScore, confidenceScore } = simulation;
  let verdict: ScoutOutput['verdict'];
  let verdictReason: string;

  if (riskScore < 0.35 && confidenceScore >= 0.65) {
    verdict = 'green';
    verdictReason = `Low risk (${(riskScore * 100).toFixed(0)}%) with solid confidence. MAO ${fmt(simulation.recommendedMao)} looks defensible.`;
  } else if (riskScore < 0.6) {
    verdict = 'yellow';
    verdictReason = `Moderate risk (${(riskScore * 100).toFixed(0)}%). Proceed with caution — verify rehab and ARV independently.`;
  } else {
    verdict = 'red';
    verdictReason = `High risk (${(riskScore * 100).toFixed(0)}%). Deal likely not viable at current ask.`;
  }

  return { simulation, verdict, verdictReason, priorDeals, marketContext };
}

// ─── Disposition Matcher tools ────────────────────────────────────────────────

export interface MatcherInput {
  zip:      string;
  strategy: string;
  mao:      number;
  arv:      number;
}

export interface BuyerMatch {
  source:    'graph' | 'vector';
  id:        string;
  name?:     string;
  score?:    number;
  metadata?: Record<string, unknown>;
}

export interface MatcherOutput {
  buyers:      BuyerMatch[];
  totalFound:  number;
  topPick?:    BuyerMatch;
  recommendation: string;
}

export async function runDispositionMatcher(input: MatcherInput): Promise<MatcherOutput> {
  const query = `cash buyer ${input.strategy} ${input.zip} ARV ${input.arv}`;

  const [graphBuyers, vectorBuyers] = await Promise.all([
    findBuyersForZip(input.zip).catch(() => [] as { buyerId: string; name?: string }[]),
    searchBuyers(query, { zip: input.zip }, 10).catch(() => []),
  ]);

  const buyers: BuyerMatch[] = [
    ...graphBuyers.map((b) => ({
      source: 'graph' as const,
      id:     b.buyerId,
      name:   b.name,
    })),
    ...vectorBuyers.map((b) => ({
      source:   'vector' as const,
      id:       b.id,
      score:    b.score,
      metadata: b.metadata as Record<string, unknown> | undefined,
    })),
  ];

  const topPick = buyers.sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0];
  const totalFound = buyers.length;

  const recommendation = totalFound === 0
    ? `No active buyers found in ZIP ${input.zip}. Consider expanding to adjacent ZIPs or direct mail campaign.`
    : `${totalFound} buyer signal(s) found. Top match: ${topPick?.name ?? topPick?.id ?? 'unknown'}. Recommend direct outreach with assignment fee target based on ${fmt(input.mao)} MAO.`;

  return { buyers, totalFound, topPick, recommendation };
}

// ─── Deal Negotiator tools ────────────────────────────────────────────────────

export interface NegotiatorInput {
  property:      Property;
  currentOffer:  number;
  sellerAsk:     number;
  marketRegime?: MarketRegime;
}

export interface CounterRange {
  floor:   number;   // walk-away threshold
  target:  number;   // ideal counter
  ceiling: number;   // max defensible offer
}

export interface NegotiatorOutput {
  counterRange:  CounterRange;
  rationale:     string;
  simulation:    SimulationResult;
  shouldCounter: boolean;
}

export async function runDealNegotiator(input: NegotiatorInput): Promise<NegotiatorOutput> {
  const weights = await WeightsRepo.getLatest().catch(() => null) ?? DEFAULT_WEIGHTS;
  const simulation = simulate(input.property, weights, input.marketRegime ?? 'neutral');

  const mao      = simulation.recommendedMao;
  const ceiling  = simulation.aggressive.mao;
  const floor    = simulation.conservative.mao;
  const target   = Math.round((mao * 0.95) / 500) * 500; // 5% below MAO, rounded to $500

  const shouldCounter = input.sellerAsk > ceiling
    ? false   // seller is too far above ceiling
    : input.sellerAsk > mao;

  let rationale: string;
  if (!shouldCounter) {
    if (input.sellerAsk <= mao) {
      rationale = `Seller ask of ${fmt(input.sellerAsk)} is within MAO (${fmt(mao)}). Accept or counter minimally at ${fmt(target)}.`;
    } else {
      rationale = `Seller ask of ${fmt(input.sellerAsk)} exceeds max ceiling (${fmt(ceiling)}). Deal not viable — recommend walking away.`;
    }
  } else {
    rationale = `Counter at ${fmt(target)}. MAO ceiling is ${fmt(mao)}, aggressive ceiling is ${fmt(ceiling)}. Do not exceed ${fmt(mao)} to preserve minimum margin.`;
  }

  return {
    counterRange: { floor, target, ceiling },
    rationale,
    simulation,
    shouldCounter,
  };
}

// ─── Shared ───────────────────────────────────────────────────────────────────

function fmt(n: number): string {
  return `$${n.toLocaleString()}`;
}
