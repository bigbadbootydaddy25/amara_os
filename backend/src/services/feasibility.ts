export type ParcelForScore = {
  area_acres: number | null;
  est_max_lot_count: number | null;
  zoning_code: string | null;
  allowed_use_category: string | null;
  is_tax_delinquent: boolean | null;
  has_code_violations: boolean | null;
  years_owned: number | null;
  flood_zone_code: string | null;
  topography_class: string | null;
  estimated_land_value_per_potential_lot: number | null;
  nearby_new_build_price_per_unit: number | null;
};

export type FeasibilityResult = {
  score: number;
  recommendation: "GO" | "MAYBE" | "PASS";
};

export function computeFeasibilityScore(p: ParcelForScore): FeasibilityResult {
  let score = 50;

  // Lot count range bonus
  if (p.est_max_lot_count && p.est_max_lot_count >= 5 && p.est_max_lot_count <= 40) score += 10;
  if (p.est_max_lot_count && p.est_max_lot_count > 40) score += 5;

  // Zoning completeness penalty
  if (!p.zoning_code || !p.allowed_use_category) score -= 10;

  // Distress opportunity bonuses
  if (p.is_tax_delinquent) score += 8;
  if (p.has_code_violations) score += 6;
  if (p.years_owned && p.years_owned >= 10) score += 5;

  // Physical risk deductions
  if (p.flood_zone_code && p.flood_zone_code !== "X") score -= 10;
  if (p.topography_class === "STEEP") score -= 10;

  // Land-to-retail ratio scoring
  if (
    p.estimated_land_value_per_potential_lot &&
    p.nearby_new_build_price_per_unit &&
    p.nearby_new_build_price_per_unit > 0
  ) {
    const landToRetailRatio =
      p.estimated_land_value_per_potential_lot / p.nearby_new_build_price_per_unit;
    if (landToRetailRatio <= 0.1) score += 15;
    else if (landToRetailRatio <= 0.15) score += 8;
    else if (landToRetailRatio > 0.25) score -= 10;
  }

  score = Math.max(0, Math.min(100, score));

  let recommendation: "GO" | "MAYBE" | "PASS";
  if (score >= 75) recommendation = "GO";
  else if (score >= 55) recommendation = "MAYBE";
  else recommendation = "PASS";

  return { score, recommendation };
}

/**
 * Converts Drizzle row (camelCase) to the snake_case shape expected by the scorer.
 */
export function parcelRowToScoreInput(row: {
  areaAcres?: number | null;
  estMaxLotCount?: number | null;
  zoningCode?: string | null;
  allowedUseCategory?: string | null;
  isTaxDelinquent?: boolean | null;
  hasCodeViolations?: boolean | null;
  yearsOwned?: string | number | null;
  floodZoneCode?: string | null;
  topographyClass?: string | null;
  estimatedLandValuePerPotentialLot?: string | number | null;
  nearbyNewBuildPricePerUnit?: string | number | null;
}): ParcelForScore {
  return {
    area_acres: row.areaAcres ?? null,
    est_max_lot_count: row.estMaxLotCount ?? null,
    zoning_code: row.zoningCode ?? null,
    allowed_use_category: row.allowedUseCategory ?? null,
    is_tax_delinquent: row.isTaxDelinquent ?? null,
    has_code_violations: row.hasCodeViolations ?? null,
    years_owned: row.yearsOwned != null ? Number(row.yearsOwned) : null,
    flood_zone_code: row.floodZoneCode ?? null,
    topography_class: row.topographyClass ?? null,
    estimated_land_value_per_potential_lot:
      row.estimatedLandValuePerPotentialLot != null
        ? Number(row.estimatedLandValuePerPotentialLot)
        : null,
    nearby_new_build_price_per_unit:
      row.nearbyNewBuildPricePerUnit != null
        ? Number(row.nearbyNewBuildPricePerUnit)
        : null,
  };
}
