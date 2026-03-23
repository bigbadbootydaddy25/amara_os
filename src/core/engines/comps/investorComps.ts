/**
 * AMARA OS — Investor Comps Engine
 * What will an investor buyer actually pay?
 * Uses cash-buyer behavior, not retail MLS logic.
 */

import { SourceConfidence } from "@/core/schema/canonical";

export interface InvestorSale {
  id: string;
  address: string;
  zip: string;
  salePrice: number;
  saleDate: string;
  beds: number;
  baths: number;
  sqft: number;
  yearBuilt: number;
  distanceMiles: number;
  buyerType: "LLC" | "CORP" | "CASH_INDIVIDUAL" | "UNKNOWN";
  isCashPurchase: boolean;
  condition: "DISTRESSED" | "STANDARD" | "RENOVATED" | "UNKNOWN";
  postSaleFlipped: boolean;         // did buyer resell within 18 months?
  postSaleRented: boolean;          // did buyer rent it?
}

export interface InvestorResaleResult {
  investorResaleLow: number;
  investorResaleMid: number;
  investorResaleHigh: number;
  pricePerSqft: number;
  salesUsed: number;
  confidence: SourceConfidence;
  discountFromARV: number | null;    // how much below ARV investors typically buy
  methodology: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// INVESTOR RESALE ESTIMATOR
// ─────────────────────────────────────────────────────────────────────────────
// When no investor comp data is available, estimate from ARV with a discount
const INVESTOR_DISCOUNT_BY_REHAB: Record<string, number> = {
  LIPSTICK:  0.85,   // 15% below ARV
  COSMETIC:  0.78,   // 22% below ARV
  MODERATE:  0.72,   // 28% below ARV
  FULL_GUT:  0.65,   // 35% below ARV
  UNKNOWN:   0.75,   // 25% below ARV default
};

export function estimateInvestorResaleFromARV(
  arv: number,
  rehabGrade: string
): { estimate: number; low: number; high: number; confidence: SourceConfidence } {
  const pct = INVESTOR_DISCOUNT_BY_REHAB[rehabGrade] ?? 0.75;
  const estimate = Math.round(arv * pct);
  return {
    estimate,
    low: Math.round(estimate * 0.93),
    high: Math.round(estimate * 1.07),
    confidence: "MEDIUM",
  };
}

export function calculateInvestorResale(
  subjectSqft: number,
  subjectZip: string,
  sales: InvestorSale[],
  maxRadiusMiles = 1.0,
  maxAgeDays = 365
): InvestorResaleResult {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - maxAgeDays);

  // Filter: only cash/investor sales, within radius, recent
  const filtered = sales.filter((s) => {
    if (!s.isCashPurchase && s.buyerType === "UNKNOWN") return false;
    if (s.distanceMiles > maxRadiusMiles) return false;
    if (new Date(s.saleDate) < cutoff) return false;
    if (s.condition === "RENOVATED") return false; // want as-is investor buys
    const sqftDiff = Math.abs(s.sqft - subjectSqft) / subjectSqft;
    return sqftDiff <= 0.25;
  });

  if (filtered.length < 2) {
    return {
      investorResaleLow: 0,
      investorResaleMid: 0,
      investorResaleHigh: 0,
      pricePerSqft: 0,
      salesUsed: 0,
      confidence: "LOW",
      discountFromARV: null,
      methodology: "INSUFFICIENT_INVESTOR_SALES",
    };
  }

  const ppsfValues = filtered.map((s) => s.salePrice / s.sqft);
  const sorted = [...ppsfValues].sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)];
  const p25 = sorted[Math.floor(sorted.length * 0.25)];
  const p75 = sorted[Math.floor(sorted.length * 0.75)];

  return {
    investorResaleLow: Math.round(p25 * subjectSqft),
    investorResaleMid: Math.round(median * subjectSqft),
    investorResaleHigh: Math.round(p75 * subjectSqft),
    pricePerSqft: Math.round(median),
    salesUsed: filtered.length,
    confidence: filtered.length >= 4 ? "HIGH" : "MEDIUM",
    discountFromARV: null,
    methodology: `${filtered.length} investor cash sales | ${Math.round(p25)}–${Math.round(p75)} $/sqft`,
  };
}
