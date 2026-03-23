/**
 * AMARA OS — Market Schema
 * Models the 37 virtual markets and their scoring for weekly closing potential.
 */

export type MarketStatus = "ACTIVE_SCAN" | "QUEUED" | "PAUSED" | "ERROR";

export interface MarketProfile {
  id: string;
  label: string;           // e.g. "DFW", "Phoenix", "Houston"
  state: string;
  metros: string[];
  zips: string[];          // ZIP codes in this market
  status: MarketStatus;

  // Scoring for weekly closings
  weeklyClosingScore: number;        // 0–100
  closingVelocityRank: number;       // 1 = best market for quick close
  cashBuyerDensity: "HIGH" | "MEDIUM" | "LOW";
  olderHousingStockPct: number;      // % of stock built pre-1985
  investorZIPCount: number;          // ZIPs with active investor activity
  avgDOMOnDistress: number;          // avg days on market for distressed
  priceReducedInventoryPct: number;  // % of active listings with reductions

  // Disqualifiers
  disqualified: boolean;
  disqualifyReasons: string[];

  // Scan state
  lastScanAt: string | null;
  nextScanAt: string | null;
  dealsFoundLast7Days: number;
  dealsFoundLast30Days: number;
  sourceHealth: Record<string, "OK" | "DEGRADED" | "ERROR" | "OFFLINE">;

  // Source adapters configured for this market
  enabledSources: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// MARKET QUALIFICATION RULES
// ─────────────────────────────────────────────────────────────────────────────
export const MARKET_QUALIFICATION = {
  // Required for a market to be active
  minCashBuyerDensity: "MEDIUM" as const,
  minOlderHousingStockPct: 0.25,        // at least 25% pre-1985 stock
  maxAvgDOMOnDistress: 90,              // distressed deals must move faster than 90 days
  minInvestorZIPCount: 3,               // at least 3 investor-active ZIPs

  // Disqualifiers
  disqualifyIfAvgPriceTooHigh: 800_000, // average price above this = luxury market
  disqualifyIfNoCashBuyers: true,
} as const;

// ─────────────────────────────────────────────────────────────────────────────
// INITIAL 37 MARKET SEEDS
// ─────────────────────────────────────────────────────────────────────────────
export const INITIAL_MARKETS: Pick<MarketProfile, "id" | "label" | "state" | "metros">[] = [
  { id: "dfw", label: "DFW", state: "TX", metros: ["Dallas", "Fort Worth", "Arlington"] },
  { id: "houston", label: "Houston", state: "TX", metros: ["Houston", "Katy", "Sugar Land", "Pearland"] },
  { id: "san_antonio", label: "San Antonio", state: "TX", metros: ["San Antonio", "New Braunfels"] },
  { id: "austin", label: "Austin", state: "TX", metros: ["Austin", "Round Rock", "Kyle", "Pflugerville"] },
  { id: "phoenix", label: "Phoenix", state: "AZ", metros: ["Phoenix", "Mesa", "Glendale", "Scottsdale", "Tempe"] },
  { id: "tucson", label: "Tucson", state: "AZ", metros: ["Tucson", "Oro Valley"] },
  { id: "las_vegas", label: "Las Vegas", state: "NV", metros: ["Las Vegas", "Henderson", "North Las Vegas"] },
  { id: "reno", label: "Reno", state: "NV", metros: ["Reno", "Sparks"] },
  { id: "atlanta", label: "Atlanta", state: "GA", metros: ["Atlanta", "Marietta", "Decatur", "Smyrna"] },
  { id: "charlotte", label: "Charlotte", state: "NC", metros: ["Charlotte", "Concord", "Gastonia"] },
  { id: "raleigh", label: "Raleigh", state: "NC", metros: ["Raleigh", "Durham", "Cary"] },
  { id: "jacksonville", label: "Jacksonville", state: "FL", metros: ["Jacksonville", "Orange Park"] },
  { id: "tampa", label: "Tampa", state: "FL", metros: ["Tampa", "St. Petersburg", "Clearwater"] },
  { id: "orlando", label: "Orlando", state: "FL", metros: ["Orlando", "Kissimmee", "Sanford"] },
  { id: "miami", label: "Miami", state: "FL", metros: ["Miami", "Hialeah", "Coral Gables"] },
  { id: "memphis", label: "Memphis", state: "TN", metros: ["Memphis"] },
  { id: "nashville", label: "Nashville", state: "TN", metros: ["Nashville", "Murfreesboro", "Franklin"] },
  { id: "kansas_city", label: "Kansas City", state: "MO", metros: ["Kansas City", "Overland Park", "Olathe"] },
  { id: "st_louis", label: "St. Louis", state: "MO", metros: ["St. Louis", "St. Charles", "Florissant"] },
  { id: "indianapolis", label: "Indianapolis", state: "IN", metros: ["Indianapolis", "Carmel", "Fishers"] },
  { id: "columbus", label: "Columbus", state: "OH", metros: ["Columbus", "Dublin", "Westerville"] },
  { id: "cleveland", label: "Cleveland", state: "OH", metros: ["Cleveland", "Akron", "Parma"] },
  { id: "detroit", label: "Detroit", state: "MI", metros: ["Detroit", "Warren", "Sterling Heights"] },
  { id: "chicago", label: "Chicago", state: "IL", metros: ["Chicago", "Aurora", "Rockford"] },
  { id: "milwaukee", label: "Milwaukee", state: "WI", metros: ["Milwaukee", "Madison"] },
  { id: "minneapolis", label: "Minneapolis", state: "MN", metros: ["Minneapolis", "St. Paul", "Bloomington"] },
  { id: "denver", label: "Denver", state: "CO", metros: ["Denver", "Aurora", "Lakewood"] },
  { id: "colorado_springs", label: "Colorado Springs", state: "CO", metros: ["Colorado Springs", "Pueblo"] },
  { id: "albuquerque", label: "Albuquerque", state: "NM", metros: ["Albuquerque", "Rio Rancho"] },
  { id: "oklahoma_city", label: "Oklahoma City", state: "OK", metros: ["Oklahoma City", "Edmond", "Norman"] },
  { id: "tulsa", label: "Tulsa", state: "OK", metros: ["Tulsa", "Broken Arrow"] },
  { id: "birmingham", label: "Birmingham", state: "AL", metros: ["Birmingham", "Hoover", "Tuscaloosa"] },
  { id: "louisville", label: "Louisville", state: "KY", metros: ["Louisville", "Lexington"] },
  { id: "richmond", label: "Richmond", state: "VA", metros: ["Richmond", "Virginia Beach", "Norfolk"] },
  { id: "baltimore", label: "Baltimore", state: "MD", metros: ["Baltimore", "Towson", "Columbia"] },
  { id: "philadelphia", label: "Philadelphia", state: "PA", metros: ["Philadelphia", "Pittsburgh", "Allentown"] },
  { id: "pittsburgh", label: "Pittsburgh", state: "PA", metros: ["Pittsburgh", "Allentown"] },
];
