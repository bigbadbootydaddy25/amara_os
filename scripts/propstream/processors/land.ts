// ─────────────────────────────────────────────────────────────────────────────
// Land / Dead Paper Track Processor
// Classifies land records, scores urgency, flags ghost subdivisions
// ─────────────────────────────────────────────────────────────────────────────

import type {
  NormalisedRecord,
  LandTarget,
  LandClassification,
  DeadPaperTarget,
  GhostSubdivisionTarget,
} from "../types/index.js";
import { resolveZip } from "../config/zips.js";
import { LAND_LISTS } from "../config/lists.js";

// ── Classification ─────────────────────────────────────────────────────────────

function classifyLand(rec: NormalisedRecord): LandClassification {
  const type = (rec.propertyType ?? "").toLowerCase();
  const distress = rec.distressIndicators.join(" ").toLowerCase();
  const rawText = JSON.stringify(rec.raw.fields).toLowerCase();

  if (/ghost|zero permit|no permit|no building/i.test(rawText)) {
    return "ghost_subdivision";
  }
  if (/stalled|halted|suspended|abandoned subdivision/i.test(rawText)) {
    return "stalled_subdivision";
  }
  if (/dead paper|paper subdivision|unrecorded/i.test(rawText)) {
    return "dead_paper_subdivision";
  }
  if (/tentative map|tent\.? map/i.test(rawText)) {
    return "expiring_tentative_map";
  }
  if (/finished lot|pad|ready to build/i.test(rawText)) {
    return "finished_lot";
  }
  if (/infill|urban lot|in-fill/i.test(rawText)) {
    return "infill_lot";
  }
  if (/builder|expansion|edge/i.test(rawText)) {
    return "builder_edge_expansion";
  }
  if (rec.lotCount && rec.lotCount > 1) {
    return "paper_lot";
  }
  // Fallback based on acreage
  if (rec.acreage) {
    if (rec.acreage < 0.5) return "infill_lot";
    if (rec.acreage < 5)   return "vacant_land";
    return "vacant_land";
  }
  return "vacant_land";
}

// ── Distress signals ───────────────────────────────────────────────────────────

function detectLandDistressSignals(rec: NormalisedRecord): string[] {
  const signals: string[] = [...rec.distressIndicators];
  const rawText = JSON.stringify(rec.raw.fields).toLowerCase();

  if (rec.taxDelinquentAmount && rec.taxDelinquentAmount > 0) {
    signals.push("delinquent_taxes");
  }
  if (/revok|inactive|dissolv|cancel/i.test(rawText)) {
    signals.push("owner_entity_revoked");
  }
  if (/bankruptcy|bk\b|chapter 7|chapter 11/i.test(rawText)) {
    signals.push("owner_bankruptcy");
  }
  if (/litigation|lawsuit|lis pendens|judgment/i.test(rawText)) {
    signals.push("owner_in_litigation");
  }
  if (/tentative map/i.test(rawText) && /18 month|approved/i.test(rawText)) {
    signals.push("tentative_map_over_18mo");
  }
  if (/recorded plat/i.test(rawText) && /zero permit|no permit/i.test(rawText)) {
    signals.push("recorded_plat_no_permits");
  }

  // Adjacent parcels / assemblage (heuristic: same owner with multiple records)
  // This is set by the caller after grouping — see processLandTrack()

  return [...new Set(signals)];
}

// ── Urgency Scoring ────────────────────────────────────────────────────────────

function scoreUrgency(
  classification: LandClassification,
  signals: string[],
  rec: NormalisedRecord
): { score: number; reason: string; daysToExpiry: number | null } {
  let score = 0;
  let reason = "";
  let daysToExpiry: number | null = null;

  // Expiry calculations
  if (rec.approvalDate && classification === "expiring_tentative_map") {
    const approved = new Date(rec.approvalDate);
    const now = new Date();
    const monthsSinceApproval =
      (now.getTime() - approved.getTime()) / (1000 * 60 * 60 * 24 * 30);
    // Tentative maps typically expire at 24 months
    const monthsToExpiry = 24 - monthsSinceApproval;
    daysToExpiry = Math.floor(monthsToExpiry * 30);

    if (daysToExpiry <= 0) {
      score = 100;
      reason = "Entitlement expired";
    } else if (daysToExpiry <= 30) {
      score = 95;
      reason = `${daysToExpiry} days to expiry`;
    } else if (daysToExpiry <= 60) {
      score = 85;
      reason = `${daysToExpiry} days to expiry`;
    } else if (daysToExpiry <= 90) {
      score = 75;
      reason = `${daysToExpiry} days to expiry`;
    }
  }

  // Classification base scores
  if (score === 0) {
    switch (classification) {
      case "ghost_subdivision":        score = 80; reason = "Ghost subdivision — plat with no permits"; break;
      case "dead_paper_subdivision":   score = 75; reason = "Dead paper subdivision"; break;
      case "stalled_subdivision":      score = 70; reason = "Stalled subdivision"; break;
      case "expiring_tentative_map":   score = 65; reason = "Tentative map — expiry window unknown"; break;
      case "paper_lot":                score = 55; reason = "Paper lot with distress signals"; break;
      default:                         score = 30; reason = classification; break;
    }
  }

  // Bonus for compounding distress
  if (signals.includes("delinquent_taxes"))      score = Math.min(100, score + 10);
  if (signals.includes("owner_entity_revoked"))  score = Math.min(100, score + 8);
  if (signals.includes("owner_bankruptcy"))      score = Math.min(100, score + 12);
  if (signals.includes("owner_in_litigation"))   score = Math.min(100, score + 6);
  if (signals.includes("recorded_plat_no_permits")) score = Math.min(100, score + 15);

  return { score, reason, daysToExpiry };
}

// ── Main export ────────────────────────────────────────────────────────────────

export interface LandProcessorResult {
  allLandTargets:         LandTarget[];
  deadPaperTargets:       DeadPaperTarget[];
  ghostSubdivisionTargets: GhostSubdivisionTarget[];
}

export function processLandTrack(records: NormalisedRecord[]): LandProcessorResult {
  const landRecords = records.filter((r) => {
    if (!LAND_LISTS.includes(r.listType)) return false;
    const zipInfo = resolveZip(r.zip);
    return zipInfo.inScope || zipInfo.isPriorityCorridorForLand;
  });

  // Group by owner to flag adjacent parcel assemblage potential
  const ownerGroups = new Map<string, NormalisedRecord[]>();
  for (const rec of landRecords) {
    const key = (rec.ownerEntityName ?? rec.ownerName ?? "unknown").toLowerCase().trim();
    if (!ownerGroups.has(key)) ownerGroups.set(key, []);
    ownerGroups.get(key)!.push(rec);
  }

  const allLandTargets: LandTarget[] = [];
  const deadPaperTargets: DeadPaperTarget[] = [];
  const ghostSubdivisionTargets: GhostSubdivisionTarget[] = [];

  for (const rec of landRecords) {
    const zipInfo = resolveZip(rec.zip);
    const classification = classifyLand(rec);
    let signals = detectLandDistressSignals(rec);

    // Flag assemblage potential
    const ownerKey = (rec.ownerEntityName ?? rec.ownerName ?? "").toLowerCase().trim();
    const ownerGroup = ownerGroups.get(ownerKey) ?? [];
    if (ownerGroup.length > 2) {
      signals.push("adjacent_parcels_same_owner");
    }
    signals = [...new Set(signals)];

    const { score, reason, daysToExpiry } = scoreUrgency(classification, signals, rec);

    const base: LandTarget = {
      address:          rec.address,
      apn:              rec.apn ?? null,
      zip:              rec.zip,
      county:           rec.county ?? null,
      city:             rec.city,
      state:            rec.state,
      lotSizeRaw:       rec.lotSizeRaw ?? null,
      acreage:          rec.acreage ?? null,
      lotCount:         rec.lotCount ?? null,
      zoning:           rec.zoning ?? null,
      classification,
      distressType:     rec.listType,
      distressSignals:  signals,
      ownerEntityName:  rec.ownerEntityName ?? rec.ownerName ?? null,
      price:            rec.price ?? null,
      assessedValue:    rec.assessedValue ?? null,
      approvalDate:     rec.approvalDate ?? null,
      permitActivity:   rec.permitActivity ?? null,
      listType:         rec.listType,
      incomplete:       rec.incomplete,
      tier:             zipInfo.isPriorityCorridorForLand
                          ? "priority_corridor"
                          : (zipInfo.tier ?? "tier2"),
      market:           zipInfo.market ?? "Unknown",
    };

    allLandTargets.push(base);

    // Dead paper track
    if (
      ["dead_paper_subdivision","ghost_subdivision","stalled_subdivision","expiring_tentative_map"]
        .includes(classification)
    ) {
      const dp: DeadPaperTarget = {
        ...base,
        classification: classification as DeadPaperTarget["classification"],
        daysToExpiry,
        urgencyScore: score,
        urgencyReason: reason,
      };
      deadPaperTargets.push(dp);
    }

    // Ghost subdivision track
    if (classification === "ghost_subdivision") {
      const gs: GhostSubdivisionTarget = {
        ...base,
        classification: "ghost_subdivision",
        recordedPlatDate: rec.approvalDate ?? rec.recordingDate ?? null,
        permitsConfirmed: false,
        urgencyScore: score,
      };
      ghostSubdivisionTargets.push(gs);
    }
  }

  // Sort dead paper by urgency descending
  deadPaperTargets.sort((a, b) => b.urgencyScore - a.urgencyScore);

  return { allLandTargets, deadPaperTargets, ghostSubdivisionTargets };
}

export function groupLandByZip(targets: LandTarget[]): Map<string, LandTarget[]> {
  const map = new Map<string, LandTarget[]>();
  for (const t of targets) {
    if (!map.has(t.zip)) map.set(t.zip, []);
    map.get(t.zip)!.push(t);
  }
  return map;
}
