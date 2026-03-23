/**
 * AMARA OS — Scan Orchestrator
 * Runs all 37 virtual markets through the autonomous pipeline.
 * AMARA scans. AMARA scores. AMARA surfaces deals. You close.
 */

import { SEEDED_MARKET_SCORES } from "@/core/engines/market/marketSelector";
import { ZillowScanConfig } from "@/adapters/zillow/ZillowPlaywright";
import { CanonicalDeal, emptyDistress, emptyValuation } from "@/core/schema/canonical";
import { ZillowRawListing } from "@/adapters/zillow/types";
import { runPipeline, PipelineResult } from "@/core/pipeline/dealPipeline";
import { v4 as uuid } from "uuid";

// ─────────────────────────────────────────────────────────────────────────────
// SCAN STATE (in-memory — replace with DB in production)
// ─────────────────────────────────────────────────────────────────────────────
export interface MarketScanState {
  marketId: string;
  label: string;
  status: "IDLE" | "SCANNING" | "PROCESSING" | "COMPLETE" | "ERROR";
  startedAt: string | null;
  completedAt: string | null;
  listingsFound: number;
  dealsQualified: number;
  lastError: string | null;
}

export interface ScanSession {
  sessionId: string;
  startedAt: string;
  completedAt: string | null;
  status: "RUNNING" | "COMPLETE" | "ERROR" | "PARTIAL";
  marketsScanned: number;
  totalListings: number;
  totalDealsQualified: number;
  marketStates: MarketScanState[];
  deals: CanonicalDeal[];
}

// Global scan state
let activeScanSession: ScanSession | null = null;

export function getActiveScan(): ScanSession | null {
  return activeScanSession;
}

export function getScanStatus(): {
  isRunning: boolean;
  session: ScanSession | null;
} {
  return {
    isRunning: activeScanSession?.status === "RUNNING",
    session: activeScanSession,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// NORMALIZE RAW ZILLOW → Partial<CanonicalDeal>
// ─────────────────────────────────────────────────────────────────────────────
function normalizeZillowListing(
  listing: ZillowRawListing,
  market: { id: string; label: string; state: string },
  zip: string
): Partial<CanonicalDeal> {
  // Parse price string "$185,000" → 185000
  const parsePrice = (s: string | null): number | null => {
    if (!s) return null;
    const n = parseFloat(s.replace(/[$,]/g, ""));
    return isNaN(n) ? null : n;
  };

  // Parse DOM "67 days on Zillow" → 67
  const parseDom = (s: string | null): number | null => {
    if (!s) return null;
    const m = s.match(/(\d+)/);
    return m ? parseInt(m[1]) : null;
  };

  // Parse details "3 bds · 2 ba · 1,480 sqft"
  const parseBeds = (details: string | null): number | null => {
    if (!details) return null;
    const m = details.match(/(\d+)\s*bd/i);
    return m ? parseInt(m[1]) : null;
  };
  const parseBaths = (details: string | null): number | null => {
    if (!details) return null;
    const m = details.match(/(\d+)\s*ba/i);
    return m ? parseInt(m[1]) : null;
  };
  const parseSqft = (details: string | null): number | null => {
    if (!details) return null;
    const m = details.match(/([\d,]+)\s*sqft/i);
    return m ? parseFloat(m[1].replace(/,/g, "")) : null;
  };
  const parseYearBuilt = (s: string | null): number | null => {
    if (!s) return null;
    const m = s.match(/\d{4}/);
    return m ? parseInt(m[0]) : null;
  };

  const listPrice = parsePrice(listing.price);
  const dom = parseDom(listing.dom);
  const beds = parseBeds(listing.details);
  const baths = parseBaths(listing.details);
  const sqft = parseSqft(listing.details);
  const yearBuilt = parseYearBuilt(listing.yearBuilt ?? null);
  const zestimate = parsePrice(listing.zestimate ?? null);

  // Derive address components from the full address
  // Zillow address format: "4821 Hickory Creek Dr, Dallas, TX 75228"
  const addrParts = listing.address?.split(",").map(s => s.trim()) ?? [];
  const streetAddress = addrParts[0] ?? listing.address ?? "";
  const cityPart = addrParts[1] ?? "";
  const stateZipPart = addrParts[2] ?? "";
  const stateMatch = stateZipPart.match(/([A-Z]{2})\s*(\d{5})/);
  const detectedState = stateMatch?.[1] ?? market.state;
  const detectedZip = stateMatch?.[2] ?? zip;

  // Price reduction detection from price history
  const priceReductions = (listing.priceHistoryRows ?? [])
    .filter(row => row.toLowerCase().includes("price change") || row.toLowerCase().includes("reduc"))
    .length;

  return {
    id: uuid(),
    sources: ["zillow"],
    primarySource: "zillow",
    sourceConfidence: "MEDIUM",
    sourceIds: {
      zillow: listing.zpid ?? null,
      propstream: null, propelio: null, public_records: null, xleads: null, manual: null,
    },
    sourceUrls: { zillow: listing.detailUrl ?? null },
    address: streetAddress,
    city: cityPart,
    state: detectedState,
    zip: detectedZip,
    county: "",
    market: market.id,
    propertyType: "SFR", // Zillow default — enriched later
    beds,
    baths,
    livingAreaSqft: sqft,
    yearBuilt,
    listingStatus: listing.status === "Pending" ? "PENDING" : "ACTIVE",
    listPrice,
    originalListPrice: listPrice, // will be updated if price history shows reductions
    dom,
    cdom: dom,
    remarks: listing.remarks ?? null,
    priceHistory: (listing.priceHistoryRows ?? []).map(row => ({
      date: new Date().toISOString(),
      price: 0,
      event: row.toLowerCase().includes("list") ? "LISTED" : "REDUCED" as "LISTED" | "REDUCED",
    })),
    valuation: {
      ...emptyValuation(),
      avm: zestimate,
      avmSource: zestimate ? "zillow_zestimate" : null,
      avmConfidence: zestimate ? "MEDIUM" as const : "LOW" as const,
      investorResaleEstimate: zestimate ? Math.round(zestimate * 0.78) : null, // cosmetic-grade estimate
      rehabEstimate: sqft ? Math.round(sqft * 25) : 30000, // $25/sqft rough estimate
      rehabGrade: "COSMETIC" as const,
    },
    distress: {
      ...emptyDistress(),
      priceReduced: listing.priceReduced,
      priceReductionCount: priceReductions,
    },
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// SCAN A SINGLE MARKET
// ─────────────────────────────────────────────────────────────────────────────
async function scanMarket(
  market: typeof SEEDED_MARKET_SCORES[0],
  state: MarketScanState
): Promise<PipelineResult> {
  state.status = "SCANNING";
  state.startedAt = new Date().toISOString();

  try {
    // Import Playwright scanner dynamically (only when actually scanning)
    const { scanZillowMarket } = await import("@/adapters/zillow/ZillowPlaywright");

    const config: ZillowScanConfig = {
      market: market.label,
      state: market.state,
      zips: market.zips.slice(0, 6), // Scan first 6 ZIPs per market per run
      minDom: 30,
      priceReduced: true,
      maxPrice: 600_000,
      minPrice: 40_000,
      maxPages: 2,
    };

    console.log(`[AMARA:Scan] Starting ${market.label} — ${config.zips.length} ZIPs`);
    const rawListings = await scanZillowMarket(config);
    state.listingsFound = rawListings.length;
    console.log(`[AMARA:Scan] ${market.label}: ${rawListings.length} raw listings found`);

    // Normalize to canonical
    state.status = "PROCESSING";
    const normalized = rawListings.map(listing =>
      normalizeZillowListing(listing, market, config.zips[0])
    );

    // Run through deal pipeline
    const result = await runPipeline(normalized, { market: market.id, source: "zillow" });

    state.status = "COMPLETE";
    state.dealsQualified = result.qualified;
    state.completedAt = new Date().toISOString();

    return result;

  } catch (err) {
    state.status = "ERROR";
    state.lastError = (err as Error).message ?? "unknown error";
    state.completedAt = new Date().toISOString();
    console.error(`[AMARA:Scan] ${market.label} error:`, err);
    return {
      processed: 0, qualified: 0, rejected: 0,
      rejectionReasons: {}, deals: [], durationMs: 0,
    };
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// FULL MARKET SCAN — All 37 Markets
// ─────────────────────────────────────────────────────────────────────────────
export async function runFullMarketScan(options?: {
  tierFilter?: string;   // "TIER_1_PRIORITY" | "TIER_2_ACTIVE" | etc.
  marketIds?: string[];  // scan only specific markets
  maxMarkets?: number;   // cap total markets per run
}): Promise<ScanSession> {
  if (activeScanSession?.status === "RUNNING") {
    console.log("[AMARA:Scan] Scan already running — skipping");
    return activeScanSession;
  }

  const sessionId = uuid();
  const now = new Date().toISOString();

  // Filter markets to scan
  let marketsToScan = SEEDED_MARKET_SCORES;

  if (options?.marketIds?.length) {
    marketsToScan = marketsToScan.filter(m => options.marketIds!.includes(m.id));
  } else if (options?.tierFilter) {
    marketsToScan = marketsToScan.filter(m => m.tier === options.tierFilter);
  }

  if (options?.maxMarkets) {
    marketsToScan = marketsToScan.slice(0, options.maxMarkets);
  }

  console.log(`[AMARA:Scan] Session ${sessionId} — scanning ${marketsToScan.length} markets`);

  const marketStates: MarketScanState[] = marketsToScan.map(m => ({
    marketId: m.id,
    label: m.label,
    status: "IDLE",
    startedAt: null,
    completedAt: null,
    listingsFound: 0,
    dealsQualified: 0,
    lastError: null,
  }));

  activeScanSession = {
    sessionId,
    startedAt: now,
    completedAt: null,
    status: "RUNNING",
    marketsScanned: 0,
    totalListings: 0,
    totalDealsQualified: 0,
    marketStates,
    deals: [],
  };

  // Scan markets sequentially (rate limit compliance — Zillow enforces ~8 req/min)
  // For production: use Redis queue + worker pool
  for (let i = 0; i < marketsToScan.length; i++) {
    const market = marketsToScan[i];
    const state = marketStates[i];

    const result = await scanMarket(market, state);

    activeScanSession.marketsScanned++;
    activeScanSession.totalListings += result.processed;
    activeScanSession.totalDealsQualified += result.qualified;
    activeScanSession.deals.push(...result.deals);

    // Pause between markets (rate limiting + stealth)
    if (i < marketsToScan.length - 1) {
      await sleep(5000 + Math.random() * 3000);
    }
  }

  activeScanSession.status = activeScanSession.marketStates.some(s => s.status === "ERROR")
    ? "PARTIAL"
    : "COMPLETE";
  activeScanSession.completedAt = new Date().toISOString();

  console.log(
    `[AMARA:Scan] Session complete: ${activeScanSession.totalDealsQualified} deals qualified from ${activeScanSession.totalListings} listings across ${activeScanSession.marketsScanned} markets`
  );

  return activeScanSession;
}

// ─────────────────────────────────────────────────────────────────────────────
// TIER-1-ONLY QUICK SCAN (for fast daily runs)
// ─────────────────────────────────────────────────────────────────────────────
export async function runTier1Scan(): Promise<ScanSession> {
  return runFullMarketScan({ tierFilter: "TIER_1_PRIORITY" });
}

// ─────────────────────────────────────────────────────────────────────────────
// SINGLE MARKET SCAN
// ─────────────────────────────────────────────────────────────────────────────
export async function runSingleMarketScan(marketId: string): Promise<ScanSession> {
  return runFullMarketScan({ marketIds: [marketId] });
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}
