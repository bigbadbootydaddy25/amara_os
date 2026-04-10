// ─────────────────────────────────────────────────────────────────────────────
// Target ZIP code configuration — all markets, tiered by priority
// ─────────────────────────────────────────────────────────────────────────────

export interface MarketConfig {
  market: string;
  state: string;
  tier: "tier1" | "tier2";
  zips: string[];
}

export const MARKETS: MarketConfig[] = [
  // ── Tier 1 Primary ─────────────────────────────────────────────────────────
  {
    market: "Las Vegas NV",
    state: "NV",
    tier: "tier1",
    zips: ["89030","89031","89032","89110","89115","89156","89104","89106","89101","89108","89107"],
  },
  {
    market: "Phoenix AZ",
    state: "AZ",
    tier: "tier1",
    zips: ["85009","85015","85017","85021","85031","85033","85035","85041"],
  },
  {
    market: "Dallas TX",
    state: "TX",
    tier: "tier1",
    zips: ["75210","75215","75216","75217","75227","75232","75241","75211","75212","75208"],
  },
  {
    market: "Houston TX",
    state: "TX",
    tier: "tier1",
    zips: ["77051","77033","77021","77028","77087","77048","77053","77013","77015","77029","77016","77026","77093"],
  },
  {
    market: "San Antonio TX",
    state: "TX",
    tier: "tier1",
    zips: ["78207","78210","78220","78227","78228","78237"],
  },
  // ── Tier 1 Midwest ─────────────────────────────────────────────────────────
  {
    market: "Detroit MI",
    state: "MI",
    tier: "tier1",
    zips: ["48205","48213","48224","48234"],
  },
  {
    market: "Columbus OH",
    state: "OH",
    tier: "tier1",
    zips: ["43207","43211","43223","43228"],
  },
  {
    market: "Indianapolis IN",
    state: "IN",
    tier: "tier1",
    zips: ["46218","46222","46227","46241"],
  },
  {
    market: "Dayton OH",
    state: "OH",
    tier: "tier1",
    zips: ["45402","45405","45406","45417"],
  },
  {
    market: "Louisville KY",
    state: "KY",
    tier: "tier1",
    zips: ["40211","40212","40215","40216"],
  },
  {
    market: "Cleveland OH",
    state: "OH",
    tier: "tier1",
    zips: ["44104","44108","44112","44120"],
  },
  // ── Tier 1 Southeast ────────────────────────────────────────────────────────
  {
    market: "Tampa FL",
    state: "FL",
    tier: "tier1",
    zips: ["33605","33610","33612","33619"],
  },
  {
    market: "Orlando FL",
    state: "FL",
    tier: "tier1",
    zips: ["32805","32808","32811","32818"],
  },
  {
    market: "Jacksonville FL",
    state: "FL",
    tier: "tier1",
    zips: ["32208","32209","32210","32218"],
  },
  {
    market: "Port St Lucie FL",
    state: "FL",
    tier: "tier1",
    zips: ["34952","34953","34983","34984"],
  },
  {
    market: "Charlotte NC",
    state: "NC",
    tier: "tier1",
    zips: ["28205","28208","28212","28216"],
  },
  {
    market: "Fayetteville NC",
    state: "NC",
    tier: "tier1",
    zips: ["28301","28303","28304","28306"],
  },
  {
    market: "Atlanta GA",
    state: "GA",
    tier: "tier1",
    zips: ["30310","30314","30315","30318"],
  },
  {
    market: "Clarksville TN",
    state: "TN",
    tier: "tier1",
    zips: ["37040","37042","37043"],
  },
  {
    market: "Knoxville TN",
    state: "TN",
    tier: "tier1",
    zips: ["37917","37921","37920"],
  },
  // ── Tier 2 Expansion ───────────────────────────────────────────────────────
  {
    market: "St Louis MO",
    state: "MO",
    tier: "tier2",
    zips: ["63106","63107","63113","63115"],
  },
  {
    market: "Kansas City MO",
    state: "MO",
    tier: "tier2",
    zips: ["64128","64130","64132","64134"],
  },
  {
    market: "Birmingham AL",
    state: "AL",
    tier: "tier2",
    zips: ["35208","35211","35214","35228"],
  },
  {
    market: "Pittsburgh PA",
    state: "PA",
    tier: "tier2",
    zips: ["15210","15212","15219","15221"],
  },
  {
    market: "Little Rock AR",
    state: "AR",
    tier: "tier2",
    zips: ["72204","72205","72206","72209"],
  },
  {
    market: "Shreveport LA",
    state: "LA",
    tier: "tier2",
    zips: ["71101","71103","71104","71106"],
  },
];

// Priority corridors for land / dead paper (may overlap with markets above)
export const PRIORITY_CORRIDORS: Array<{ label: string; zips: string[] }> = [
  { label: "Dallas outer-south",     zips: ["75241","75232","75217"] },
  { label: "Houston fringe",         zips: ["77053","77048","77093"] },
  { label: "Las Vegas edge",         zips: ["89156","89115","89110"] },
];

// Flat lookup structures built once at startup
export const ALL_ZIPS = new Set(MARKETS.flatMap((m) => m.zips));

export const ZIP_TO_MARKET = new Map<string, MarketConfig>(
  MARKETS.flatMap((m) => m.zips.map((z) => [z, m]))
);

export const PRIORITY_CORRIDOR_ZIPS = new Set(
  PRIORITY_CORRIDORS.flatMap((c) => c.zips)
);

export function resolveZip(zip: string): {
  inScope: boolean;
  market: string | null;
  tier: "tier1" | "tier2" | null;
  isPriorityCorridorForLand: boolean;
} {
  const market = ZIP_TO_MARKET.get(zip);
  return {
    inScope: !!market,
    market: market?.market ?? null,
    tier: market?.tier ?? null,
    isPriorityCorridorForLand: PRIORITY_CORRIDOR_ZIPS.has(zip),
  };
}
