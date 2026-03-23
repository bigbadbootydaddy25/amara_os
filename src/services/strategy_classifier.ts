/**
 * StrategyClassifier
 *
 * Classifies a buyer's investment strategy from behavioral signals
 * observed in their actual transaction history. Returns a confidence
 * score alongside the classification so callers can apply their own
 * threshold gates.
 *
 * No strategy is assigned without supporting evidence. When signals
 * are mixed or insufficient, the classifier returns 'unknown'.
 *
 * Signal sources (all derived from transaction records):
 *   - Property type distribution
 *   - Price tier and spread
 *   - Entity name keywords (builder, fund, etc.)
 *   - Acquisition pace and frequency
 *   - Land / teardown acquisition patterns
 *   - Portfolio concentration (few ZIPs vs. scattered)
 */

import type { BuyerStrategy } from '../models/buybox';
import type { PropertyType } from '../models/transaction';
import type { VerificationFlags } from '../models/buyer';

export interface StrategySignals {
  // From buy box
  propertyTypes: Array<{ property_type: PropertyType; pct_of_total: number }>;
  priceAvg: number | null;
  priceSpreadRatio: number | null;  // (p75 - p25) / median — measures diversity
  acquisitionsPerYear: number | null;
  uniqueZipCount: number;
  totalTransactions: number;

  // From buyer entity
  entityFlags: Pick<
    VerificationFlags,
    'is_builder_developer' | 'is_institutional' | 'transaction_pace_per_year'
  >;
}

export interface ClassificationResult {
  strategy: BuyerStrategy;
  confidence: number;   // 0–1
  signals: string[];    // human-readable evidence trail
}

// ─── Signal weights ───────────────────────────────────────────────────────────
// Each strategy accumulates evidence points; the winner is the strategy with
// the most points. Confidence = winner_points / total_possible_points (capped 1).

interface StrategyEvidence {
  points: number;
  signals: string[];
}

type EvidenceMap = Partial<Record<BuyerStrategy, StrategyEvidence>>;

function addEvidence(
  map: EvidenceMap,
  strategy: BuyerStrategy,
  points: number,
  signal: string
): void {
  const existing = map[strategy] ?? { points: 0, signals: [] };
  existing.points += points;
  existing.signals.push(signal);
  map[strategy] = existing;
}

// ─── Classifier ──────────────────────────────────────────────────────────────

export function classifyStrategy(signals: StrategySignals): ClassificationResult {
  const evidence: EvidenceMap = {};

  const { propertyTypes, priceAvg, priceSpreadRatio, acquisitionsPerYear,
          uniqueZipCount, totalTransactions, entityFlags } = signals;

  const pctByType = new Map(propertyTypes.map((p) => [p.property_type, p.pct_of_total]));

  // ── Builder / Developer ─────────────────────────────────────────────────
  if (entityFlags.is_builder_developer) {
    addEvidence(evidence, 'new_construction', 30, 'entity name contains builder/developer keywords');
  }
  if ((pctByType.get('land') ?? 0) >= 40) {
    addEvidence(evidence, 'new_construction', 20, '40%+ of acquisitions are land');
    addEvidence(evidence, 'land_banking', 10, '40%+ of acquisitions are land');
  }
  if ((pctByType.get('land') ?? 0) >= 70) {
    addEvidence(evidence, 'land_banking', 20, '70%+ of acquisitions are land');
  }

  // ── Institutional SFR ───────────────────────────────────────────────────
  if (entityFlags.is_institutional) {
    addEvidence(evidence, 'institutional_sfr', 25, 'entity name contains institutional/fund keywords');
  }
  if (acquisitionsPerYear !== null && acquisitionsPerYear >= 20) {
    addEvidence(evidence, 'institutional_sfr', 20, `high acquisition pace: ${acquisitionsPerYear.toFixed(1)}/yr`);
  }
  if (totalTransactions >= 50) {
    addEvidence(evidence, 'institutional_sfr', 15, `large portfolio: ${totalTransactions} transactions`);
  }

  // ── Rental Portfolio ────────────────────────────────────────────────────
  const mfrPct = pctByType.get('mfr') ?? 0;
  const sfrPct = pctByType.get('sfr') ?? 0;

  if (mfrPct >= 30) {
    addEvidence(evidence, 'rental_portfolio', 20, `${mfrPct}% multi-family acquisitions`);
  }
  if (sfrPct >= 60 && (acquisitionsPerYear ?? 0) >= 3 && totalTransactions >= 5) {
    addEvidence(evidence, 'rental_portfolio', 15, 'consistent SFR acquisitions suggesting hold strategy');
  }
  // Geographic concentration = portfolio building in a market
  if (uniqueZipCount <= 3 && totalTransactions >= 4) {
    addEvidence(evidence, 'rental_portfolio', 10, `concentrated in ≤3 ZIPs with ${totalTransactions} transactions`);
  }

  // ── Fix and Flip ────────────────────────────────────────────────────────
  if (priceAvg !== null && priceAvg < 250_000 && sfrPct >= 50) {
    addEvidence(evidence, 'fix_and_flip', 15, `avg price $${priceAvg.toLocaleString()} in SFR — typical flip range`);
  }
  if (priceSpreadRatio !== null && priceSpreadRatio > 0.4) {
    addEvidence(evidence, 'fix_and_flip', 10, 'high price spread suggests opportunistic buying');
  }
  if (acquisitionsPerYear !== null && acquisitionsPerYear >= 4 && acquisitionsPerYear < 20) {
    addEvidence(evidence, 'fix_and_flip', 10, `acquisition pace ${acquisitionsPerYear.toFixed(1)}/yr consistent with flip cadence`);
  }

  // ── Wholesale ───────────────────────────────────────────────────────────
  if (acquisitionsPerYear !== null && acquisitionsPerYear >= 8 && priceAvg !== null && priceAvg < 150_000) {
    addEvidence(evidence, 'wholesale', 20, `high pace (${acquisitionsPerYear.toFixed(1)}/yr) + low avg price ($${priceAvg.toLocaleString()})`);
  }
  if (uniqueZipCount >= 5 && totalTransactions >= 8) {
    addEvidence(evidence, 'wholesale', 8, 'scattered ZIP pattern suggests wholesale sourcing');
  }

  // ── Mixed portfolio ─────────────────────────────────────────────────────
  const distinctTypes = propertyTypes.filter((p) => p.pct_of_total >= 15).length;
  if (distinctTypes >= 3) {
    addEvidence(evidence, 'mixed_portfolio', 15, `${distinctTypes} property types each ≥15% of portfolio`);
  }

  // ── Pick winner ─────────────────────────────────────────────────────────
  const sorted = (Object.entries(evidence) as [BuyerStrategy, StrategyEvidence][])
    .sort((a, b) => b[1].points - a[1].points);

  if (sorted.length === 0 || (sorted[0]?.points ?? 0) === 0) {
    return { strategy: 'unknown', confidence: 0, signals: ['insufficient signals'] };
  }

  const [topStrategy, topEvidence] = sorted[0]!;
  const totalPossible = 50; // rough max for any single strategy

  // If top two strategies are within 5 points, call it mixed
  const runnerUp = sorted[1];
  if (runnerUp && (topEvidence.points - runnerUp[1].points) <= 5 && topEvidence.points < 30) {
    return {
      strategy: 'mixed_portfolio',
      confidence: Math.min(topEvidence.points / totalPossible, 0.6),
      signals: [...topEvidence.signals, `competing signal: ${sorted[1]![0]}`],
    };
  }

  return {
    strategy: topStrategy,
    confidence: Math.min(topEvidence.points / totalPossible, 1),
    signals: topEvidence.signals,
  };
}

// ─── DB update helper ─────────────────────────────────────────────────────────

import { query } from '../db/client';

export async function applyStrategyToBuyBox(
  buyerEntityId: string,
  result: ClassificationResult
): Promise<void> {
  await query(
    `UPDATE buy_boxes
     SET inferred_strategy   = $1,
         strategy_confidence = $2
     WHERE buyer_entity_id   = $3`,
    [result.strategy, result.confidence, buyerEntityId]
  );
}
