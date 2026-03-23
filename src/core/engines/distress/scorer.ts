/**
 * AMARA OS — Distress Scorer
 * Combines all distress signals into a unified score and decision.
 */

import {
  CanonicalDeal,
  DistressSignals,
  emptyDistress,
} from "@/core/schema/canonical";
import { scanKeywords } from "./keywords";

// ─────────────────────────────────────────────────────────────────────────────
// DOM BUCKET SCORING
// ─────────────────────────────────────────────────────────────────────────────
function domScore(dom: number): { score: number; bucket: DistressSignals["domBucket"] } {
  if (dom >= 180) return { score: 20, bucket: "180+" };
  if (dom >= 120) return { score: 17, bucket: "120+" };
  if (dom >= 90)  return { score: 15, bucket: "90+" };
  if (dom >= 60)  return { score: 12, bucket: "60+" };
  if (dom >= 45)  return { score: 9,  bucket: "45+" };
  if (dom >= 30)  return { score: 6,  bucket: "30+" };
  return { score: 0, bucket: "FRESH" };
}

// ─────────────────────────────────────────────────────────────────────────────
// PRICE REDUCTION SCORING
// ─────────────────────────────────────────────────────────────────────────────
function priceReductionScore(reductionPct: number, count: number): number {
  let score = 0;
  if (reductionPct >= 0.15) score += 15;
  else if (reductionPct >= 0.10) score += 12;
  else if (reductionPct >= 0.05) score += 8;
  else if (reductionPct > 0) score += 4;
  // Bonus for multiple reductions
  if (count >= 3) score += 8;
  else if (count >= 2) score += 4;
  return score;
}

// ─────────────────────────────────────────────────────────────────────────────
// OWNERSHIP / PUBLIC RECORD SCORING
// ─────────────────────────────────────────────────────────────────────────────
function ownershipScore(signals: Partial<DistressSignals>): number {
  let score = 0;
  if (signals.absenteeOwner)     score += 8;
  if (signals.outOfStateOwner)   score += 6;
  if (signals.taxDelinquent)     score += 15;
  if (signals.preforeclosure)    score += 18;
  if (signals.foreclosure)       score += 20;
  if (signals.auction)           score += 18;
  if (signals.lis_pendens)       score += 18;
  if (signals.probate)           score += 16;
  if (signals.estate)            score += 14;
  if (signals.inherited)         score += 14;
  if (signals.liens)             score += 8;
  if (signals.codeViolation)     score += 10;
  if (signals.vacancy)           score += 8;
  if (signals.tenantOccupied)    score += 6;
  return score;
}

// ─────────────────────────────────────────────────────────────────────────────
// YEAR BUILT SCORING
// Older housing stock is higher distress probability
// ─────────────────────────────────────────────────────────────────────────────
function yearBuiltScore(yearBuilt: number | null): number {
  if (!yearBuilt) return 0;
  if (yearBuilt <= 1950) return 10;
  if (yearBuilt <= 1965) return 8;
  if (yearBuilt <= 1975) return 6;
  if (yearBuilt <= 1985) return 4;
  if (yearBuilt <= 1995) return 2;
  return 0;
}

// ─────────────────────────────────────────────────────────────────────────────
// MAIN DISTRESS SCORER
// ─────────────────────────────────────────────────────────────────────────────
export interface DistressScoreInput {
  remarks: string | null;
  dom: number | null;
  cdom: number | null;
  priceReductionCount: number;
  priceReductionTotalPct: number;
  yearBuilt: number | null;

  // Ownership / public record flags
  absenteeOwner?: boolean;
  outOfStateOwner?: boolean;
  corporateOwner?: boolean;
  taxDelinquent?: boolean;
  taxDelinquentAmount?: number;
  preforeclosure?: boolean;
  foreclosure?: boolean;
  auction?: boolean;
  lis_pendens?: boolean;
  probate?: boolean;
  estate?: boolean;
  inherited?: boolean;
  codeViolation?: boolean;
  vacancy?: boolean;
  tenantOccupied?: boolean;
  liens?: boolean;
  lienCount?: number;
  openLienAmount?: number;
}

export function scoreDistress(input: DistressScoreInput): DistressSignals {
  const result: DistressSignals = emptyDistress();

  // Keyword scan
  const keywordResult = scanKeywords(input.remarks ?? "");
  result.distressKeywordsFound = keywordResult.matched;
  result.keywordDistressScore = keywordResult.score;

  // Extract specific flags from keywords
  if (keywordResult.matched.includes("probate")) result.probate = true;
  if (keywordResult.matched.includes("estate sale")) result.estate = true;
  if (keywordResult.matched.includes("inherited")) result.inherited = true;
  if (keywordResult.matched.includes("foreclosure")) result.foreclosure = true;
  if (keywordResult.matched.includes("preforeclosure")) result.preforeclosure = true;
  if (keywordResult.matched.includes("short sale")) result.preforeclosure = true;
  if (keywordResult.matched.includes("tenant-occupied")) result.tenantOccupied = true;
  if (keywordResult.matched.includes("vacant")) result.vacancy = true;

  // DOM
  const effectiveDom = input.cdom ?? input.dom ?? 0;
  const domResult = domScore(effectiveDom);
  result.domDays = effectiveDom;
  result.domBucket = domResult.bucket;

  // Price reductions
  result.priceReduced = input.priceReductionCount > 0;
  result.priceReductionCount = input.priceReductionCount;
  result.priceReductionTotalPct = input.priceReductionTotalPct;

  // Ownership flags (from public records / source data)
  result.absenteeOwner = input.absenteeOwner ?? result.absenteeOwner;
  result.outOfStateOwner = input.outOfStateOwner ?? result.outOfStateOwner;
  result.corporateOwner = input.corporateOwner ?? result.corporateOwner;
  result.taxDelinquent = input.taxDelinquent ?? result.taxDelinquent;
  result.taxDelinquentAmountUSD = input.taxDelinquentAmount ?? null;
  result.preforeclosure = input.preforeclosure ?? result.preforeclosure;
  result.foreclosure = input.foreclosure ?? result.foreclosure;
  result.auction = input.auction ?? result.auction;
  result.lis_pendens = input.lis_pendens ?? result.lis_pendens;
  result.probate = input.probate ?? result.probate;
  result.estate = input.estate ?? result.estate;
  result.inherited = input.inherited ?? result.inherited;
  result.codeViolation = input.codeViolation ?? result.codeViolation;
  result.vacancy = input.vacancy ?? result.vacancy;
  result.tenantOccupied = input.tenantOccupied ?? result.tenantOccupied;
  result.liens = input.liens ?? result.liens;
  result.lienCount = input.lienCount ?? result.lienCount;
  result.openLienAmountUSD = input.openLienAmount ?? null;

  // Landlord fatigue: absentee + long DOM + at least 1 price reduction
  result.landlordFatigue =
    result.absenteeOwner &&
    effectiveDom >= 45 &&
    result.priceReduced;

  // Composite score
  const score =
    result.keywordDistressScore * 0.30 +                                  // 30% weight
    domResult.score * 0.20 +                                              // 20% weight
    priceReductionScore(result.priceReductionTotalPct, result.priceReductionCount) * 0.15 + // 15%
    ownershipScore(result) * 0.25 +                                       // 25% weight
    yearBuiltScore(input.yearBuilt) * 0.10;                               // 10% weight

  result.totalDistressScore = Math.min(100, Math.round(score));

  return result;
}

// ─────────────────────────────────────────────────────────────────────────────
// DISTRESS GATE — minimum score to pass into deal engine
// ─────────────────────────────────────────────────────────────────────────────
export const DISTRESS_GATE_MIN_SCORE = 25;

export function passesDistressGate(
  distress: DistressSignals,
  hasRetailSignals: boolean
): { passes: boolean; reason: string } {
  if (hasRetailSignals && distress.totalDistressScore < 30) {
    return { passes: false, reason: "retail-clean listing with no offsetting distress" };
  }
  if (distress.totalDistressScore < DISTRESS_GATE_MIN_SCORE) {
    return {
      passes: false,
      reason: `distress score ${distress.totalDistressScore} < minimum ${DISTRESS_GATE_MIN_SCORE}`,
    };
  }
  return { passes: true, reason: "" };
}
