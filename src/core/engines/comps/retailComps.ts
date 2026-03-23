/**
 * AMARA OS — Retail / ARV Comps Engine
 * Used for: flip exits, retail-based valuations
 * Priority: solds > pendings > actives
 */

import { SourceConfidence } from "@/core/schema/canonical";

export interface Comp {
  id: string;
  address: string;
  zip: string;
  salePrice: number;
  saleDate: string;         // ISO date
  beds: number;
  baths: number;
  sqft: number;
  yearBuilt: number;
  distanceMiles: number;
  condition: "RENOVATED" | "STANDARD" | "DISTRESSED" | "UNKNOWN";
  status: "SOLD" | "PENDING" | "ACTIVE";
  pricePerSqft: number;
}

export interface ARVCompsResult {
  arvLow: number;
  arvMid: number;
  arvHigh: number;
  pricePerSqft: number;
  compsUsed: number;
  compsTotal: number;
  confidence: SourceConfidence;
  outlierCount: number;
  methodology: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// COMP FILTER RULES
// ─────────────────────────────────────────────────────────────────────────────
export interface CompFilterCriteria {
  subjectSqft: number;
  subjectBeds: number;
  subjectBaths: number;
  subjectYearBuilt: number;
  maxRadiusMiles: number;       // default 0.5
  maxAgeDays: number;           // default 180
  sqftTolerancePct: number;     // default 0.20 (±20%)
  requireRenovated: boolean;    // for ARV: use renovated comps
}

export function filterComps(comps: Comp[], criteria: CompFilterCriteria): Comp[] {
  const cutoffDate = new Date();
  cutoffDate.setDate(cutoffDate.getDate() - criteria.maxAgeDays);

  return comps.filter((c) => {
    // Age filter
    if (new Date(c.saleDate) < cutoffDate) return false;

    // Distance filter
    if (c.distanceMiles > criteria.maxRadiusMiles) return false;

    // Sqft tolerance
    const sqftDiff = Math.abs(c.sqft - criteria.subjectSqft) / criteria.subjectSqft;
    if (sqftDiff > criteria.sqftTolerancePct) return false;

    // Bed/bath proximity (allow ±1)
    if (Math.abs(c.beds - criteria.subjectBeds) > 1) return false;
    if (Math.abs(c.baths - criteria.subjectBaths) > 1) return false;

    // Condition filter for ARV
    if (criteria.requireRenovated && c.condition === "DISTRESSED") return false;

    return true;
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// OUTLIER REJECTION (IQR method)
// ─────────────────────────────────────────────────────────────────────────────
export function rejectOutliers(prices: number[]): {
  filtered: number[];
  outlierCount: number;
} {
  if (prices.length < 4) return { filtered: prices, outlierCount: 0 };

  const sorted = [...prices].sort((a, b) => a - b);
  const q1 = sorted[Math.floor(sorted.length * 0.25)];
  const q3 = sorted[Math.floor(sorted.length * 0.75)];
  const iqr = q3 - q1;
  const lower = q1 - 1.5 * iqr;
  const upper = q3 + 1.5 * iqr;

  const filtered = prices.filter((p) => p >= lower && p <= upper);
  return { filtered, outlierCount: prices.length - filtered.length };
}

// ─────────────────────────────────────────────────────────────────────────────
// ARV CALCULATOR
// ─────────────────────────────────────────────────────────────────────────────
export function calculateARV(
  subjectSqft: number,
  comps: Comp[],
  criteria: CompFilterCriteria
): ARVCompsResult {
  const filtered = filterComps(comps, criteria);

  if (filtered.length === 0) {
    return {
      arvLow: 0, arvMid: 0, arvHigh: 0,
      pricePerSqft: 0,
      compsUsed: 0, compsTotal: comps.length,
      confidence: "LOW",
      outlierCount: 0,
      methodology: "INSUFFICIENT_COMPS",
    };
  }

  // Weight by recency and status: SOLD > PENDING > ACTIVE
  const weighted = filtered.map((c) => {
    const statusWeight = c.status === "SOLD" ? 1.0 : c.status === "PENDING" ? 0.8 : 0.6;
    const ageWeight = 1 - (
      (Date.now() - new Date(c.saleDate).getTime()) / (criteria.maxAgeDays * 86400000)
    ) * 0.3;
    return { comp: c, weight: statusWeight * ageWeight };
  });

  const ppsfValues = weighted.map((w) => w.comp.pricePerSqft);
  const { filtered: cleanPpsf, outlierCount } = rejectOutliers(ppsfValues);

  if (cleanPpsf.length === 0) {
    return {
      arvLow: 0, arvMid: 0, arvHigh: 0,
      pricePerSqft: 0,
      compsUsed: 0, compsTotal: comps.length,
      confidence: "LOW",
      outlierCount,
      methodology: "ALL_OUTLIERS",
    };
  }

  const sorted = [...cleanPpsf].sort((a, b) => a - b);
  const medianPpsf = sorted[Math.floor(sorted.length / 2)];
  const p25Ppsf = sorted[Math.floor(sorted.length * 0.25)];
  const p75Ppsf = sorted[Math.floor(sorted.length * 0.75)];

  const arvLow  = Math.round(p25Ppsf * subjectSqft);
  const arvMid  = Math.round(medianPpsf * subjectSqft);
  const arvHigh = Math.round(p75Ppsf * subjectSqft);

  const confidence: SourceConfidence =
    cleanPpsf.length >= 5 ? "HIGH" :
    cleanPpsf.length >= 3 ? "MEDIUM" : "LOW";

  return {
    arvLow, arvMid, arvHigh,
    pricePerSqft: Math.round(medianPpsf),
    compsUsed: cleanPpsf.length,
    compsTotal: comps.length,
    confidence,
    outlierCount,
    methodology: `${cleanPpsf.length} comps | ${Math.round(p25Ppsf)}–${Math.round(p75Ppsf)} $/sqft | ${criteria.requireRenovated ? "RENOVATED" : "ALL"} condition`,
  };
}
