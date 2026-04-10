// ─────────────────────────────────────────────────────────────────────────────
// Match Board — cross-references targets against buyer profiles per ZIP
// Urgency scoring for land/dead paper with immediate-action flagging
// ─────────────────────────────────────────────────────────────────────────────

import type {
  SFRTarget,
  LandTarget,
  SFRBuyer,
  LandBuyer,
  SFRMatch,
  BuilderMatch,
  DeadPaperTarget,
} from "../types/index.js";

const IMMEDIATE_ACTION_THRESHOLD = 75;

// ── SFR Match Board ────────────────────────────────────────────────────────────

export function buildSFRMatchBoard(
  targets: SFRTarget[],
  buyers: SFRBuyer[]
): SFRMatch[] {
  const matches: SFRMatch[] = [];

  for (const property of targets) {
    const matchedBuyers = buyers.filter((b) =>
      isSFRBuyerMatch(property, b)
    );

    if (matchedBuyers.length === 0) continue;

    const { score, reasons } = scoreSFRMatch(property, matchedBuyers);

    matches.push({
      property,
      matchedBuyers,
      matchScore: score,
      matchReasons: reasons,
      zip: property.zip,
      market: property.market,
    });
  }

  // Sort by match score descending, then by number of distress indicators
  return matches.sort((a, b) => {
    if (b.matchScore !== a.matchScore) return b.matchScore - a.matchScore;
    return b.property.distressIndicators.length - a.property.distressIndicators.length;
  });
}

function isSFRBuyerMatch(property: SFRTarget, buyer: SFRBuyer): boolean {
  // Must be active in the same ZIP or an adjacent market
  if (!buyer.activeZips.includes(property.zip)) {
    // Check if buyer is active in the same market
    if (!buyer.markets.includes(property.market)) return false;
  }

  // Price range check (within 20% tolerance)
  if (buyer.priceRangeMax !== null && property.price !== null) {
    if (property.price > buyer.priceRangeMax * 1.2) return false;
  }
  if (buyer.priceRangeMin !== null && property.price !== null) {
    if (property.price < buyer.priceRangeMin * 0.8) return false;
  }

  // Property type check (if buyer specifies types)
  if (buyer.propertyTypes.length > 0 && !buyer.propertyTypes.includes("Unknown")) {
    const propType = property.propertyType.toLowerCase();
    const typeMatch = buyer.propertyTypes.some((t) =>
      propType.includes(t.toLowerCase()) || t.toLowerCase().includes(propType)
    );
    if (!typeMatch) return false;
  }

  return true;
}

function scoreSFRMatch(
  property: SFRTarget,
  buyers: SFRBuyer[]
): { score: number; reasons: string[] } {
  let score = 0;
  const reasons: string[] = [];

  // Base: distress indicators
  const distressBonus = Math.min(30, property.distressIndicators.length * 6);
  score += distressBonus;
  if (distressBonus > 0) reasons.push(`${property.distressIndicators.length} distress signals`);

  // Buyer count in ZIP
  const exactZipBuyers = buyers.filter((b) => b.activeZips.includes(property.zip));
  if (exactZipBuyers.length >= 3) {
    score += 25;
    reasons.push(`${exactZipBuyers.length} active buyers in ZIP ${property.zip}`);
  } else if (exactZipBuyers.length >= 1) {
    score += 15;
    reasons.push(`${exactZipBuyers.length} buyer(s) in ZIP ${property.zip}`);
  } else {
    score += 10;
    reasons.push(`${buyers.length} buyer(s) in market`);
  }

  // Tier bonus
  if (property.tier === "tier1") {
    score += 15;
    reasons.push("Tier 1 market");
  } else {
    score += 5;
  }

  // Price completeness
  if (property.price !== null) {
    score += 10;
    reasons.push(`Price known: $${property.price.toLocaleString()}`);
  }

  // Year built completeness
  if (property.yearBuilt !== null) {
    score += 5;
    reasons.push(`Built ${property.yearBuilt}`);
  }

  // Incomplete penalty
  if (property.incomplete) {
    score -= 10;
    reasons.push("Record flagged incomplete");
  }

  return { score: Math.max(0, Math.min(100, score)), reasons };
}

// ── Builder / Land Match Board ─────────────────────────────────────────────────

export function buildBuilderMatchBoard(
  targets: LandTarget[],
  buyers: LandBuyer[],
  deadPaperTargets: DeadPaperTarget[]
): BuilderMatch[] {
  const matches: BuilderMatch[] = [];

  // Build a lookup from dead paper by address for urgency injection
  const deadPaperMap = new Map<string, DeadPaperTarget>(
    deadPaperTargets.map((dp) => [normaliseKey(dp.address), dp])
  );

  for (const property of targets) {
    const matchedBuyers = buyers.filter((b) =>
      isLandBuyerMatch(property, b)
    );

    const deadPaper = deadPaperMap.get(normaliseKey(property.address));
    const urgencyScore = deadPaper?.urgencyScore ?? baseUrgencyScore(property);
    const urgencyReason = deadPaper?.urgencyReason ?? property.classification;

    if (matchedBuyers.length === 0 && urgencyScore < IMMEDIATE_ACTION_THRESHOLD) {
      continue; // no match and not urgent enough
    }

    const { score, reasons } = scoreLandMatch(property, matchedBuyers, urgencyScore);

    matches.push({
      property,
      matchedBuyers,
      urgencyScore,
      urgencyReason,
      matchScore: score,
      matchReasons: reasons,
      zip: property.zip,
      market: property.market,
      flagForImmediateAction: urgencyScore >= IMMEDIATE_ACTION_THRESHOLD,
    });
  }

  return matches.sort((a, b) => {
    // Immediate action first
    if (a.flagForImmediateAction !== b.flagForImmediateAction) {
      return a.flagForImmediateAction ? -1 : 1;
    }
    // Then urgency score
    if (b.urgencyScore !== a.urgencyScore) return b.urgencyScore - a.urgencyScore;
    // Then match score
    return b.matchScore - a.matchScore;
  });
}

function isLandBuyerMatch(property: LandTarget, buyer: LandBuyer): boolean {
  // ZIP or market match
  if (!buyer.activeZips.includes(property.zip)) {
    if (!buyer.markets.includes(property.market)) return false;
  }

  // Lot size range check
  if (property.acreage !== null) {
    if (buyer.lotSizeMax !== null && property.acreage > buyer.lotSizeMax * 2) return false;
    if (buyer.lotSizeMin !== null && property.acreage < buyer.lotSizeMin * 0.5) return false;
  }

  // Price range check
  if (buyer.priceRangeMax !== null && property.price !== null) {
    if (property.price > buyer.priceRangeMax * 1.3) return false;
  }

  return true;
}

function scoreLandMatch(
  property: LandTarget,
  buyers: LandBuyer[],
  urgencyScore: number
): { score: number; reasons: string[] } {
  let score = urgencyScore * 0.5; // urgency contributes half
  const reasons: string[] = [];

  // Buyer depth
  const exactZipBuyers = buyers.filter((b) => b.activeZips.includes(property.zip));
  if (exactZipBuyers.length >= 2) {
    score += 20;
    reasons.push(`${exactZipBuyers.length} land buyers in ZIP ${property.zip}`);
  } else if (exactZipBuyers.length === 1) {
    score += 12;
    reasons.push(`1 land buyer in ZIP ${property.zip}`);
  } else if (buyers.length > 0) {
    score += 6;
    reasons.push(`${buyers.length} land buyer(s) in market`);
  }

  // Priority corridor bonus
  if (property.tier === "priority_corridor") {
    score += 15;
    reasons.push("Priority corridor for land");
  } else if (property.tier === "tier1") {
    score += 10;
    reasons.push("Tier 1 market");
  }

  // Distress signal count
  const bonusDistress = Math.min(15, property.distressSignals.length * 3);
  score += bonusDistress;
  if (bonusDistress > 0) reasons.push(`${property.distressSignals.length} distress signals`);

  // Lot count / assemblage potential
  if (property.lotCount && property.lotCount > 5) {
    score += 10;
    reasons.push(`${property.lotCount} lots — assemblage potential`);
  }

  if (property.incomplete) {
    score -= 8;
    reasons.push("Record flagged incomplete");
  }

  return { score: Math.max(0, Math.min(100, score)), reasons };
}

function baseUrgencyScore(property: LandTarget): number {
  let score = 20;
  if (property.distressSignals.includes("delinquent_taxes"))      score += 15;
  if (property.distressSignals.includes("owner_entity_revoked"))  score += 12;
  if (property.distressSignals.includes("owner_bankruptcy"))      score += 18;
  if (property.distressSignals.includes("recorded_plat_no_permits")) score += 20;
  if (property.tier === "priority_corridor")                      score += 10;
  return Math.min(100, score);
}

function normaliseKey(address: string): string {
  return address.toLowerCase().replace(/[^a-z0-9]/g, "");
}

// ── ZIP-level summary ──────────────────────────────────────────────────────────

export interface ZipSummary {
  zip: string;
  market: string;
  sfrTargetCount: number;
  landTargetCount: number;
  activeSFRBuyers: number;
  activeLandBuyers: number;
  topSFRMatches: SFRMatch[];
  topBuilderMatches: BuilderMatch[];
  flaggedForImmediateAction: BuilderMatch[];
}

export function buildZipSummaries(
  sfrMatches: SFRMatch[],
  builderMatches: BuilderMatch[]
): ZipSummary[] {
  const zips = new Set([
    ...sfrMatches.map((m) => m.zip),
    ...builderMatches.map((m) => m.zip),
  ]);

  return [...zips].map((zip) => {
    const sfrInZip = sfrMatches.filter((m) => m.zip === zip);
    const bldInZip = builderMatches.filter((m) => m.zip === zip);
    const market = sfrInZip[0]?.market ?? bldInZip[0]?.market ?? "Unknown";

    const uniqueSFRBuyers = new Set(
      sfrInZip.flatMap((m) => m.matchedBuyers.map((b) => b.buyerName))
    );
    const uniqueLandBuyers = new Set(
      bldInZip.flatMap((m) => m.matchedBuyers.map((b) => b.buyerName))
    );

    return {
      zip,
      market,
      sfrTargetCount:          sfrInZip.length,
      landTargetCount:         bldInZip.length,
      activeSFRBuyers:         uniqueSFRBuyers.size,
      activeLandBuyers:        uniqueLandBuyers.size,
      topSFRMatches:           sfrInZip.slice(0, 5),
      topBuilderMatches:       bldInZip.slice(0, 5),
      flaggedForImmediateAction: bldInZip.filter((m) => m.flagForImmediateAction),
    };
  });
}
