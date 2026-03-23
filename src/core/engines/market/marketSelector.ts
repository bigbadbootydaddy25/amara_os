/**
 * AMARA OS — Market Selection Engine
 * Identifies the best markets for weekly closings.
 * Uses buyer density, distress inventory, DOM velocity, and deal flow metrics.
 */

import { MarketProfile, MARKET_QUALIFICATION, INITIAL_MARKETS } from "@/core/schema/market";

// ─────────────────────────────────────────────────────────────────────────────
// MARKET SCORING FACTORS
// ─────────────────────────────────────────────────────────────────────────────
export interface MarketScoringFactors {
  cashBuyerDensityScore: number;    // 0–25
  distressInventoryScore: number;   // 0–25
  domVelocityScore: number;         // 0–20
  olderHousingScore: number;        // 0–15
  priceReductionScore: number;      // 0–15
}

export function scoreMarket(market: MarketProfile): {
  total: number;
  factors: MarketScoringFactors;
  rank: string;
  disqualified: boolean;
  disqualifyReasons: string[];
} {
  const disqualifyReasons: string[] = [];

  // Hard disqualifiers
  if (market.cashBuyerDensity === "LOW") {
    disqualifyReasons.push("insufficient cash buyer density");
  }
  if (market.olderHousingStockPct < MARKET_QUALIFICATION.minOlderHousingStockPct) {
    disqualifyReasons.push(`older housing stock ${Math.round(market.olderHousingStockPct * 100)}% below minimum 25%`);
  }
  if (market.avgDOMOnDistress > MARKET_QUALIFICATION.maxAvgDOMOnDistress) {
    disqualifyReasons.push(`avg DOM ${market.avgDOMOnDistress} too slow for weekly closings`);
  }
  if (market.investorZIPCount < MARKET_QUALIFICATION.minInvestorZIPCount) {
    disqualifyReasons.push(`only ${market.investorZIPCount} investor ZIPs — need ${MARKET_QUALIFICATION.minInvestorZIPCount}+`);
  }

  if (disqualifyReasons.length > 0) {
    return { total: 0, factors: emptyFactors(), rank: "DISQUALIFIED", disqualified: true, disqualifyReasons };
  }

  // Scoring
  const cashScore = market.cashBuyerDensity === "HIGH" ? 25 : 15;

  const distressScore = Math.min(25,
    market.investorZIPCount * 3 +
    (market.priceReducedInventoryPct >= 0.20 ? 8 : market.priceReducedInventoryPct >= 0.12 ? 5 : 2)
  );

  const domScore = Math.min(20,
    market.avgDOMOnDistress <= 30 ? 20 :
    market.avgDOMOnDistress <= 45 ? 16 :
    market.avgDOMOnDistress <= 60 ? 12 : 8
  );

  const olderHousingScore = Math.min(15, Math.round(market.olderHousingStockPct * 40));

  const priceReductionScore = Math.min(15,
    market.priceReducedInventoryPct >= 0.25 ? 15 :
    market.priceReducedInventoryPct >= 0.15 ? 10 :
    market.priceReducedInventoryPct >= 0.08 ? 6 : 3
  );

  const total = cashScore + distressScore + domScore + olderHousingScore + priceReductionScore;
  const rank =
    total >= 80 ? "TIER_1_PRIORITY" :
    total >= 65 ? "TIER_2_ACTIVE" :
    total >= 50 ? "TIER_3_MONITOR" : "TIER_4_LOW";

  return {
    total,
    factors: { cashBuyerDensityScore: cashScore, distressInventoryScore: distressScore, domVelocityScore: domScore, olderHousingScore, priceReductionScore },
    rank,
    disqualified: false,
    disqualifyReasons: [],
  };
}

function emptyFactors(): MarketScoringFactors {
  return { cashBuyerDensityScore: 0, distressInventoryScore: 0, domVelocityScore: 0, olderHousingScore: 0, priceReductionScore: 0 };
}

// ─────────────────────────────────────────────────────────────────────────────
// SEED DATA — pre-scored markets for quick launch
// ─────────────────────────────────────────────────────────────────────────────
export const SEEDED_MARKET_SCORES: Array<{
  id: string;
  label: string;
  state: string;
  weeklyClosingScore: number;
  cashBuyerDensity: "HIGH" | "MEDIUM" | "LOW";
  olderHousingStockPct: number;
  avgDOMOnDistress: number;
  investorZIPCount: number;
  priceReducedInventoryPct: number;
  tier: string;
  why: string;
}> = [
  {
    id: "dfw", label: "DFW", state: "TX", weeklyClosingScore: 92, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.52, avgDOMOnDistress: 28, investorZIPCount: 24,
    priceReducedInventoryPct: 0.22, tier: "TIER_1_PRIORITY",
    why: "Largest TX market. High-velocity cash buyer pool. Dense investor ZIPs in Dallas/FW East Side. Repeatable weekly closings on cosmetic/fixer SFR."
  },
  {
    id: "atlanta", label: "Atlanta", state: "GA", weeklyClosingScore: 91, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.48, avgDOMOnDistress: 24, investorZIPCount: 22,
    priceReducedInventoryPct: 0.21, tier: "TIER_1_PRIORITY",
    why: "Best-in-class investor market in Southeast. Fast cash buyers. Strong flipper demand in intown and south Atlanta ZIPs."
  },
  {
    id: "phoenix", label: "Phoenix", state: "AZ", weeklyClosingScore: 89, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.44, avgDOMOnDistress: 31, investorZIPCount: 19,
    priceReducedInventoryPct: 0.24, tier: "TIER_1_PRIORITY",
    why: "High price-reduction activity in West/South Phoenix. Strong flipper demand. Fast close cycle."
  },
  {
    id: "houston", label: "Houston", state: "TX", weeklyClosingScore: 87, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.55, avgDOMOnDistress: 33, investorZIPCount: 20,
    priceReducedInventoryPct: 0.19, tier: "TIER_1_PRIORITY",
    why: "Massive older housing inventory. High absentee-owner density in East/South Houston. Active cash buyers at multiple price bands."
  },
  {
    id: "cleveland", label: "Cleveland", state: "OH", weeklyClosingScore: 85, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.78, avgDOMOnDistress: 22, investorZIPCount: 16,
    priceReducedInventoryPct: 0.28, tier: "TIER_1_PRIORITY",
    why: "Highest older housing density on list. Very low price points. Fastest DOM. Dense landlord buyer demand."
  },
  {
    id: "indianapolis", label: "Indianapolis", state: "IN", weeklyClosingScore: 83, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.56, avgDOMOnDistress: 30, investorZIPCount: 14,
    priceReducedInventoryPct: 0.20, tier: "TIER_1_PRIORITY",
    why: "Strong landlord and flipper demand. Affordable older stock. Good repeat buyer activity."
  },
  {
    id: "memphis", label: "Memphis", state: "TN", weeklyClosingScore: 82, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.65, avgDOMOnDistress: 26, investorZIPCount: 13,
    priceReducedInventoryPct: 0.26, tier: "TIER_1_PRIORITY",
    why: "High vacancy rates, high absentee ownership, dense distress. Strong landlord buyer demand."
  },
  {
    id: "kansas_city", label: "Kansas City", state: "MO", weeklyClosingScore: 79, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.58, avgDOMOnDistress: 35, investorZIPCount: 12,
    priceReducedInventoryPct: 0.18, tier: "TIER_2_ACTIVE",
    why: "Solid investor market. Older stock. Good buyer pool but slower than Tier 1."
  },
  {
    id: "detroit", label: "Detroit", state: "MI", weeklyClosingScore: 78, cashBuyerDensity: "HIGH",
    olderHousingStockPct: 0.82, avgDOMOnDistress: 21, investorZIPCount: 18,
    priceReducedInventoryPct: 0.30, tier: "TIER_2_ACTIVE",
    why: "Highest old housing %, fastest DOM. Low price points. Some neighborhood risk — need tight ZIP selection."
  },
  {
    id: "birmingham", label: "Birmingham", state: "AL", weeklyClosingScore: 77, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.61, avgDOMOnDistress: 34, investorZIPCount: 11,
    priceReducedInventoryPct: 0.22, tier: "TIER_2_ACTIVE",
    why: "Underserved investor market. High distress. Growing buyer pool."
  },
  {
    id: "tampa", label: "Tampa", state: "FL", weeklyClosingScore: 75, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.40, avgDOMOnDistress: 40, investorZIPCount: 10,
    priceReducedInventoryPct: 0.20, tier: "TIER_2_ACTIVE",
    why: "FL market with good cash buyer activity. Higher price points reduce margin. Better for flip strategy."
  },
  {
    id: "san_antonio", label: "San Antonio", state: "TX", weeklyClosingScore: 74, cashBuyerDensity: "MEDIUM",
    olderHousingStockPct: 0.47, avgDOMOnDistress: 38, investorZIPCount: 10,
    priceReducedInventoryPct: 0.17, tier: "TIER_2_ACTIVE",
    why: "Good TX secondary market. Good for Propelio targeting. Decent older stock."
  },
];

// ─────────────────────────────────────────────────────────────────────────────
// BEST MARKET RECOMMENDATION
// ─────────────────────────────────────────────────────────────────────────────
export function getBestMarketForWeeklyClosings(): typeof SEEDED_MARKET_SCORES[0] {
  return SEEDED_MARKET_SCORES
    .filter((m) => m.tier === "TIER_1_PRIORITY")
    .sort((a, b) => b.weeklyClosingScore - a.weeklyClosingScore)[0];
}
