// ─────────────────────────────────────────────────────────────────────────────
// SFR Track Processor — filters and classifies SFR / distress records
// ─────────────────────────────────────────────────────────────────────────────

import type { NormalisedRecord, SFRTarget } from "../types/index.js";
import { resolveZip } from "../config/zips.js";
import { SFR_LISTS } from "../config/lists.js";

const SFR_PROPERTY_TYPES = [
  "sfr", "single family", "single-family", "residential",
  "duplex", "2 family", "two family", "triplex", "3 family",
  "fourplex", "4 family", "small multi", "multi-family",
];

const LAND_PROPERTY_TYPES = [
  "land", "vacant land", "lot", "unimproved", "acreage",
  "farm", "ranch", "mobile home park",
];

// Built 1940–1985, price under $350K
function meetsPropertyProfile(rec: NormalisedRecord): boolean {
  if (rec.yearBuilt !== undefined) {
    if (rec.yearBuilt < 1940 || rec.yearBuilt > 1985) return false;
  }
  if (rec.price !== undefined && rec.price > 350_000) return false;
  return true;
}

function isSFRType(rec: NormalisedRecord): boolean {
  if (!rec.propertyType) return true; // assume SFR if unknown
  const t = rec.propertyType.toLowerCase();
  if (LAND_PROPERTY_TYPES.some((l) => t.includes(l))) return false;
  return SFR_PROPERTY_TYPES.some((s) => t.includes(s));
}

export function processSFRTrack(records: NormalisedRecord[]): SFRTarget[] {
  const targets: SFRTarget[] = [];

  for (const rec of records) {
    // Must be an SFR-eligible list
    if (!SFR_LISTS.includes(rec.listType)) continue;
    // Must not be a land record
    if (!isSFRType(rec)) continue;

    // ZIP must be in scope
    const zipInfo = resolveZip(rec.zip);
    if (!zipInfo.inScope) continue;

    // Must meet property profile
    if (!meetsPropertyProfile(rec)) continue;

    // Must have a usable address
    if (!rec.address || rec.address.trim() === "") continue;

    targets.push({
      address:             rec.address,
      zip:                 rec.zip,
      city:                rec.city,
      state:               rec.state,
      propertyType:        rec.propertyType ?? "Unknown",
      price:               rec.price ?? null,
      assessedValue:       rec.assessedValue ?? null,
      listType:            rec.listType,
      recordingDate:       rec.recordingDate ?? null,
      yearBuilt:           rec.yearBuilt ?? null,
      distressIndicators:  rec.distressIndicators,
      ownerName:           rec.ownerName ?? rec.ownerEntityName ?? null,
      incomplete:          rec.incomplete,
      tier:                zipInfo.tier!,
      market:              zipInfo.market!,
    });
  }

  // De-duplicate by address (keep the one with most signals)
  return deduplicateSFR(targets);
}

function deduplicateSFR(targets: SFRTarget[]): SFRTarget[] {
  const byAddress = new Map<string, SFRTarget>();

  for (const t of targets) {
    const key = normaliseAddress(t.address);
    const existing = byAddress.get(key);
    if (!existing) {
      byAddress.set(key, t);
    } else {
      // Merge distress indicators; keep the one with more data
      const merged: SFRTarget = {
        ...existing,
        distressIndicators: [
          ...new Set([...existing.distressIndicators, ...t.distressIndicators]),
        ],
        price:         existing.price ?? t.price,
        assessedValue: existing.assessedValue ?? t.assessedValue,
        yearBuilt:     existing.yearBuilt ?? t.yearBuilt,
        recordingDate: existing.recordingDate ?? t.recordingDate,
        ownerName:     existing.ownerName ?? t.ownerName,
        incomplete:    existing.incomplete && t.incomplete,
      };
      byAddress.set(key, merged);
    }
  }

  return [...byAddress.values()];
}

function normaliseAddress(address: string): string {
  return address.toLowerCase().replace(/[^a-z0-9]/g, "");
}

export function groupSFRByZip(targets: SFRTarget[]): Map<string, SFRTarget[]> {
  const map = new Map<string, SFRTarget[]>();
  for (const t of targets) {
    if (!map.has(t.zip)) map.set(t.zip, []);
    map.get(t.zip)!.push(t);
  }
  return map;
}
