/**
 * AMARA OS — Buyer Schema
 * Models active exit buyers and their buying behavior.
 * Exit buyers define what deals exist. Build this first.
 */

export type BuyerClass = "FLIPPER" | "LANDLORD" | "DEVELOPER" | "OWNER_OCCUPANT";
export type RehabTolerance = "NONE" | "COSMETIC" | "MODERATE" | "FULL_GUT" | "ANY";
export type HoldVsFlip = "HOLD" | "FLIP" | "BOTH";
export type AssetPreference = "SFR" | "MFR" | "LAND" | "LOT" | "COMMERCIAL" | "ANY";

export interface BuyerProfile {
  id: string;
  createdAt: string;
  updatedAt: string;

  // Identity
  name: string;
  entityName: string | null;        // LLC or corp name
  phone: string | null;
  email: string | null;

  // Classification
  buyerClass: BuyerClass;
  rehabTolerance: RehabTolerance;
  holdVsFlip: HoldVsFlip;
  assetPreferences: AssetPreference[];

  // Geographic targeting
  targetStates: string[];
  targetMarkets: string[];           // AMARA market labels
  targetZIPs: string[];
  radiusMiles: number | null;

  // Price band
  minPriceUSD: number | null;
  maxPriceUSD: number | null;
  typicalBidUSD: number | null;

  // Activity metrics
  purchasesLast12Months: number;
  purchasesLast24Months: number;
  lifetimePurchases: number;
  lastPurchaseDate: string | null;
  avgDaysToClose: number | null;

  // Reliability
  closingReliabilityScore: number;   // 0–100
  dispositionStrength: "STRONG" | "MODERATE" | "WEAK" | "UNKNOWN";
  isRepeatBuyer: boolean;
  isPriorityBuyer: boolean;          // 3+ in 12mo OR 2+ same ZIP cluster

  // Buy-box rules
  buyBoxNotes: string | null;
  avoidKeywords: string[];           // deal types/conditions they avoid
  requireKeywords: string[];         // must have (e.g. "3bd+", "SFR only")

  // Source tracking
  sourceMarkets: string[];
  publicRecordPurchaseAddresses: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// BUYER LANE — what demand exists at a ZIP / market level
// ─────────────────────────────────────────────────────────────────────────────
export interface BuyerLaneMarket {
  market: string;
  zip: string;
  buyerClass: BuyerClass;
  activeBuyerCount: number;
  repeatBuyerCount: number;
  avgDaysToClose: number;
  priceRangeLow: number;
  priceRangeHigh: number;
  weeklyVelocity: number;           // estimated weekly purchases in this lane
  demandStrength: "HOT" | "ACTIVE" | "MODERATE" | "COLD";
  lastUpdated: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// BUYER PRIORITY RULES
// ─────────────────────────────────────────────────────────────────────────────
export const BUYER_PRIORITY_RULES = {
  // A buyer is "priority" if they meet ANY of:
  purchases12MonthsThreshold: 3,       // 3+ buys in last 12 months
  purchases24MonthsSameZIPThreshold: 2, // 2+ in same ZIP cluster in 24 months
  lifetimePurchasesMetroThreshold: 5,  // 5+ lifetime in same metro
  maxDaysToClose: 30,                  // must be a fast closer to be priority
} as const;

export function isPriorityBuyer(buyer: BuyerProfile): boolean {
  return (
    buyer.purchasesLast12Months >= BUYER_PRIORITY_RULES.purchases12MonthsThreshold ||
    buyer.lifetimePurchases >= BUYER_PRIORITY_RULES.lifetimePurchasesMetroThreshold ||
    buyer.isRepeatBuyer
  );
}
