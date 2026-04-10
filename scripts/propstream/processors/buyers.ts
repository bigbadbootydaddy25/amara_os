// ─────────────────────────────────────────────────────────────────────────────
// Buyer Profile Builder
// Builds SFR buyer and Land/Builder buyer profiles from Cash Buyers + Flippers
// ─────────────────────────────────────────────────────────────────────────────

import type { NormalisedRecord, SFRBuyer, LandBuyer } from "../types/index.js";
import { resolveZip } from "../config/zips.js";

const LAND_KEYWORDS = /\b(land|lot|acres?|subdivision|plat|parcel|development|builder|construction|build)\b/i;
const ENTITY_KEYWORDS = /\b(LLC|Inc|Corp|LP|LLP|Trust|REIT|Properties|Holdings|Investments|Homes|Builders|Development|Capital|Ventures|Partners|Group|Realty|Fund|Assets)\b/i;

// ─── SFR Buyers ───────────────────────────────────────────────────────────────

export function buildSFRBuyerProfiles(
  cashBuyerRecords: NormalisedRecord[],
  flipperRecords: NormalisedRecord[]
): SFRBuyer[] {
  const allRecords = [...cashBuyerRecords, ...flipperRecords].filter((r) => {
    // Must be in a target ZIP
    const info = resolveZip(r.zip);
    return info.inScope;
  });

  // Group by buyer (owner name or entity)
  const buyerMap = new Map<string, NormalisedRecord[]>();
  for (const rec of allRecords) {
    const key = normaliseBuyerKey(rec.ownerEntityName ?? rec.ownerName ?? "");
    if (!key) continue;
    // Skip clear land buyers from SFR profile
    if (LAND_KEYWORDS.test(key)) continue;
    if (!buyerMap.has(key)) buyerMap.set(key, []);
    buyerMap.get(key)!.push(rec);
  }

  const profiles: SFRBuyer[] = [];
  for (const [buyerName, records] of buyerMap.entries()) {
    if (records.length === 0) continue;

    const zips = [...new Set(records.map((r) => r.zip).filter(Boolean))];
    const propertyTypes = [...new Set(records.map((r) => r.propertyType).filter(Boolean) as string[])];
    const prices = records.map((r) => r.price).filter((p): p is number => p !== undefined);
    const markets = [
      ...new Set(
        zips.map((z) => resolveZip(z).market).filter((m): m is string => !!m)
      ),
    ];

    const dates = records
      .map((r) => r.recordingDate)
      .filter(Boolean)
      .sort()
      .reverse();

    profiles.push({
      buyerName,
      entityType:        detectEntityType(buyerName, records),
      activeZips:        zips,
      propertyTypes:     propertyTypes.length > 0 ? propertyTypes : ["Unknown"],
      priceRangeMin:     prices.length > 0 ? Math.min(...prices) : null,
      priceRangeMax:     prices.length > 0 ? Math.max(...prices) : null,
      transactionCount:  records.length,
      mostRecentPurchase: dates[0] ?? null,
      markets,
    });
  }

  // Sort by transaction count descending (most active buyers first)
  return profiles.sort((a, b) => b.transactionCount - a.transactionCount);
}

// ─── Land / Builder Buyers ────────────────────────────────────────────────────

export function buildLandBuyerProfiles(
  cashBuyerRecords: NormalisedRecord[],
  flipperRecords: NormalisedRecord[]
): LandBuyer[] {
  const allRecords = [...cashBuyerRecords, ...flipperRecords].filter((r) => {
    const info = resolveZip(r.zip);
    return info.inScope || info.isPriorityCorridorForLand;
  });

  // Group by buyer
  const buyerMap = new Map<string, NormalisedRecord[]>();
  for (const rec of allRecords) {
    const key = normaliseBuyerKey(rec.ownerEntityName ?? rec.ownerName ?? "");
    if (!key) continue;

    // Only include buyers who bought land/lots OR have builder-type entity names
    const propertyIsLand =
      /\b(land|lot|acres?|vacant|unimproved|subdivision)\b/i.test(
        rec.propertyType ?? ""
      );
    const entityIsBuilder = LAND_KEYWORDS.test(key);

    if (!propertyIsLand && !entityIsBuilder) continue;

    if (!buyerMap.has(key)) buyerMap.set(key, []);
    buyerMap.get(key)!.push(rec);
  }

  const profiles: LandBuyer[] = [];
  for (const [buyerName, records] of buyerMap.entries()) {
    if (records.length === 0) continue;

    const zips = [...new Set(records.map((r) => r.zip).filter(Boolean))];
    const landTypes = [
      ...new Set(records.map((r) => r.propertyType).filter(Boolean) as string[]),
    ];
    const acreages = records
      .map((r) => r.acreage)
      .filter((a): a is number => a !== undefined && a > 0);
    const prices = records.map((r) => r.price).filter((p): p is number => p !== undefined);
    const markets = [
      ...new Set(
        zips.map((z) => resolveZip(z).market).filter((m): m is string => !!m)
      ),
    ];
    const dates = records.map((r) => r.recordingDate).filter(Boolean).sort().reverse();

    profiles.push({
      buyerName,
      entityType:        detectEntityType(buyerName, records),
      activeZips:        zips,
      landTypes:         landTypes.length > 0 ? landTypes : ["Unknown"],
      lotSizeMin:        acreages.length > 0 ? Math.min(...acreages) : null,
      lotSizeMax:        acreages.length > 0 ? Math.max(...acreages) : null,
      priceRangeMin:     prices.length > 0 ? Math.min(...prices) : null,
      priceRangeMax:     prices.length > 0 ? Math.max(...prices) : null,
      transactionCount:  records.length,
      mostRecentPurchase: dates[0] ?? null,
      markets,
    });
  }

  return profiles.sort((a, b) => b.transactionCount - a.transactionCount);
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function normaliseBuyerKey(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function detectEntityType(
  buyerName: string,
  records: NormalisedRecord[]
): string | null {
  if (/\bllc\b/i.test(buyerName)) return "LLC";
  if (/\bcorp\b|incorporated\b|inc\.?\b/i.test(buyerName)) return "Corporation";
  if (/\blp\b|\blimited partnership\b/i.test(buyerName)) return "LP";
  if (/\btrust\b/i.test(buyerName)) return "Trust";
  if (/\breit\b/i.test(buyerName)) return "REIT";
  if (ENTITY_KEYWORDS.test(buyerName)) return "Company";
  // Check entity from records
  const entityNames = records.map((r) => r.ownerEntityName).filter(Boolean);
  if (entityNames.length > 0) return "Entity";
  return "Individual";
}
