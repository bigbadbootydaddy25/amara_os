/**
 * AMARA OS — Buyer Matching Engine
 * Exit buyers first. A deal doesn't exist without an exit path.
 */

import { BuyerProfile, BuyerLaneMarket, BUYER_PRIORITY_RULES } from "@/core/schema/buyer";
import { CanonicalDeal, BuyerLane } from "@/core/schema/canonical";

// ─────────────────────────────────────────────────────────────────────────────
// BUYER MATCHING LOGIC
// ─────────────────────────────────────────────────────────────────────────────
export interface BuyerMatchInput {
  zip: string;
  market: string;
  state: string;
  propertyType: string;
  listPrice: number | null;
  arvEstimate: number | null;
  rehabGrade: string;
  distressScore: number;
  isLand: boolean;
}

export interface BuyerMatchResult {
  matched: boolean;
  buyerClass: BuyerLane["buyerClass"];
  exitConfidenceScore: number;        // 0–100
  matchedBuyerCount: number;
  matchedBuyerZIPs: string[];
  estimatedDaysToAssign: number | null;
  weeklyClosingPotential: boolean;
  reasoning: string;
}

// Mock buyer pool — in production this pulls from DB / buyer profiles
// This represents validated, repeat cash buyers in each ZIP cluster
const MOCK_BUYER_LANES: BuyerLaneMarket[] = [
  // DFW Flippers
  { market: "DFW", zip: "75228", buyerClass: "FLIPPER", activeBuyerCount: 14, repeatBuyerCount: 8, avgDaysToClose: 12, priceRangeLow: 80000, priceRangeHigh: 280000, weeklyVelocity: 3, demandStrength: "HOT", lastUpdated: new Date().toISOString() },
  { market: "DFW", zip: "75217", buyerClass: "FLIPPER", activeBuyerCount: 11, repeatBuyerCount: 6, avgDaysToClose: 14, priceRangeLow: 70000, priceRangeHigh: 250000, weeklyVelocity: 2, demandStrength: "HOT", lastUpdated: new Date().toISOString() },
  { market: "DFW", zip: "75211", buyerClass: "LANDLORD", activeBuyerCount: 8, repeatBuyerCount: 5, avgDaysToClose: 18, priceRangeLow: 85000, priceRangeHigh: 220000, weeklyVelocity: 2, demandStrength: "ACTIVE", lastUpdated: new Date().toISOString() },
  { market: "DFW", zip: "76104", buyerClass: "FLIPPER", activeBuyerCount: 9, repeatBuyerCount: 5, avgDaysToClose: 15, priceRangeLow: 60000, priceRangeHigh: 200000, weeklyVelocity: 2, demandStrength: "HOT", lastUpdated: new Date().toISOString() },
  // Houston Buyers
  { market: "Houston", zip: "77051", buyerClass: "FLIPPER", activeBuyerCount: 12, repeatBuyerCount: 7, avgDaysToClose: 13, priceRangeLow: 60000, priceRangeHigh: 200000, weeklyVelocity: 3, demandStrength: "HOT", lastUpdated: new Date().toISOString() },
  { market: "Houston", zip: "77033", buyerClass: "LANDLORD", activeBuyerCount: 9, repeatBuyerCount: 5, avgDaysToClose: 16, priceRangeLow: 65000, priceRangeHigh: 185000, weeklyVelocity: 2, demandStrength: "ACTIVE", lastUpdated: new Date().toISOString() },
  // Phoenix
  { market: "Phoenix", zip: "85031", buyerClass: "FLIPPER", activeBuyerCount: 15, repeatBuyerCount: 9, avgDaysToClose: 11, priceRangeLow: 100000, priceRangeHigh: 350000, weeklyVelocity: 4, demandStrength: "HOT", lastUpdated: new Date().toISOString() },
  { market: "Phoenix", zip: "85040", buyerClass: "FLIPPER", activeBuyerCount: 12, repeatBuyerCount: 7, avgDaysToClose: 12, priceRangeLow: 90000, priceRangeHigh: 320000, weeklyVelocity: 3, demandStrength: "HOT", lastUpdated: new Date().toISOString() },
  // Atlanta
  { market: "Atlanta", zip: "30310", buyerClass: "FLIPPER", activeBuyerCount: 16, repeatBuyerCount: 10, avgDaysToClose: 10, priceRangeLow: 50000, priceRangeHigh: 220000, weeklyVelocity: 4, demandStrength: "HOT", lastUpdated: new Date().toISOString() },
  { market: "Atlanta", zip: "30316", buyerClass: "LANDLORD", activeBuyerCount: 11, repeatBuyerCount: 6, avgDaysToClose: 14, priceRangeLow: 60000, priceRangeHigh: 200000, weeklyVelocity: 3, demandStrength: "HOT", lastUpdated: new Date().toISOString() },
  // Cleveland / Detroit (cheap cash buyer markets)
  { market: "Cleveland", zip: "44105", buyerClass: "LANDLORD", activeBuyerCount: 18, repeatBuyerCount: 12, avgDaysToClose: 8, priceRangeLow: 20000, priceRangeHigh: 95000, weeklyVelocity: 5, demandStrength: "HOT", lastUpdated: new Date().toISOString() },
  { market: "Detroit", zip: "48205", buyerClass: "LANDLORD", activeBuyerCount: 14, repeatBuyerCount: 9, avgDaysToClose: 9, priceRangeLow: 15000, priceRangeHigh: 80000, weeklyVelocity: 4, demandStrength: "HOT", lastUpdated: new Date().toISOString() },
  // Indianapolis
  { market: "Indianapolis", zip: "46218", buyerClass: "FLIPPER", activeBuyerCount: 10, repeatBuyerCount: 6, avgDaysToClose: 12, priceRangeLow: 50000, priceRangeHigh: 180000, weeklyVelocity: 3, demandStrength: "ACTIVE", lastUpdated: new Date().toISOString() },
];

export function matchBuyerLane(input: BuyerMatchInput): BuyerMatchResult {
  if (input.isLand) {
    // Land always routes to developer lane
    return {
      matched: true,
      buyerClass: "DEVELOPER",
      exitConfidenceScore: 55,
      matchedBuyerCount: 2,
      matchedBuyerZIPs: [input.zip],
      estimatedDaysToAssign: 45,
      weeklyClosingPotential: false,
      reasoning: "Land/lot routes to developer exit lane — six-figure spread targets apply",
    };
  }

  // Find buyer lanes matching this property's ZIP, market, price range
  const price = input.listPrice ?? input.arvEstimate ?? 0;

  const directMatches = MOCK_BUYER_LANES.filter((lane) => {
    const zipMatch = lane.zip === input.zip;
    const marketMatch = lane.market.toLowerCase() === input.market.toLowerCase();
    const priceMatch = price === 0 || (price >= lane.priceRangeLow * 0.7 && price <= lane.priceRangeHigh * 1.3);
    return (zipMatch || marketMatch) && priceMatch;
  });

  if (directMatches.length === 0) {
    return {
      matched: false,
      buyerClass: "UNKNOWN",
      exitConfidenceScore: 0,
      matchedBuyerCount: 0,
      matchedBuyerZIPs: [],
      estimatedDaysToAssign: null,
      weeklyClosingPotential: false,
      reasoning: "No validated buyer lane found for this ZIP/price/type combination",
    };
  }

  // Score the best match
  const best = directMatches.sort((a, b) => {
    const scoreA = a.repeatBuyerCount * 10 + a.weeklyVelocity * 5 - a.avgDaysToClose;
    const scoreB = b.repeatBuyerCount * 10 + b.weeklyVelocity * 5 - b.avgDaysToClose;
    return scoreB - scoreA;
  })[0];

  // Exit confidence scoring
  let exitScore = 0;
  if (best.demandStrength === "HOT") exitScore += 40;
  else if (best.demandStrength === "ACTIVE") exitScore += 25;
  else if (best.demandStrength === "MODERATE") exitScore += 15;

  exitScore += Math.min(30, best.repeatBuyerCount * 3);
  exitScore += Math.min(20, best.weeklyVelocity * 5);
  if (best.avgDaysToClose <= 14) exitScore += 10;
  else if (best.avgDaysToClose <= 21) exitScore += 5;

  const totalBuyers = directMatches.reduce((s, l) => s + l.activeBuyerCount, 0);
  const allZips = [...new Set(directMatches.map((l) => l.zip))];

  return {
    matched: true,
    buyerClass: best.buyerClass,
    exitConfidenceScore: Math.min(100, exitScore),
    matchedBuyerCount: totalBuyers,
    matchedBuyerZIPs: allZips,
    estimatedDaysToAssign: best.avgDaysToClose,
    weeklyClosingPotential: best.weeklyVelocity >= 2 && best.avgDaysToClose <= 21,
    reasoning: `${best.demandStrength} demand — ${best.repeatBuyerCount} repeat buyers — avg ${best.avgDaysToClose}d close in ${best.zip}`,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// BUYER GATE — no exit path = no deal shown
// ─────────────────────────────────────────────────────────────────────────────
export function passesBuyerGate(
  matchResult: BuyerMatchResult
): { passes: boolean; reason: string } {
  if (!matchResult.matched) {
    return { passes: false, reason: "no validated buyer lane — no deal without exit path" };
  }
  if (matchResult.exitConfidenceScore < 20) {
    return {
      passes: false,
      reason: `buyer confidence score ${matchResult.exitConfidenceScore} too low to surface deal`,
    };
  }
  return { passes: true, reason: "" };
}
