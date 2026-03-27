/** Full parcel record returned by GET /parcels/:id */
export interface Parcel {
  id: number;
  apn: string | null;
  addressLine1: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  county: string | null;
  jurisdiction: string | null;
  latitude: number | null;
  longitude: number | null;
  areaSqft: number | null;
  areaAcres: number | null;

  ownerName: string | null;
  ownerMailingAddress: string | null;
  lastSaleDate: string | null;
  lastSalePrice: string | null;
  assessedLandValue: string | null;
  assessedTotalValue: string | null;
  yearsOwned: string | null;

  zoningCode: string | null;
  zoningDescription: string | null;
  allowedUseCategory: string | null;
  minLotSizeSqft: number | null;
  maxUnitsPerAcre: number | null;
  floorAreaRatio: number | null;
  maxHeightFt: number | null;
  frontSetbackFt: number | null;
  sideSetbackFt: number | null;
  rearSetbackFt: number | null;

  topographyClass: string | null;
  floodZoneCode: string | null;
  hasEnvironmentalFlag: boolean | null;
  accessType: string | null;
  hasExistingStructure: boolean | null;
  existingUseType: string | null;
  existingBuildingSqft: number | null;

  hasWater: boolean | null;
  hasSewer: boolean | null;
  hasPower: boolean | null;
  hasGas: boolean | null;
  schoolDistrict: string | null;
  schoolScoreBucket: string | null;

  nearbyNewBuildPricePerUnit: string | null;
  nearbyResalePricePerSqft: string | null;
  estimatedLandValueTotal: string | null;
  estimatedLandValuePerAcre: string | null;
  estimatedLandValuePerPotentialLot: string | null;

  isTaxDelinquent: boolean | null;
  taxDelinquentAmount: string | null;
  hasCodeViolations: boolean | null;
  codeViolationCount: number | null;
  hasPreforeclosureFlag: boolean | null;
  isVacantLand: boolean | null;
  isVacantStructure: boolean | null;

  targetProductType: string | null;
  estMaxLotCount: number | null;
  estMaxUnitCount: number | null;
  feasibilityScore: number | null;
  recommendation: "GO" | "MAYBE" | "PASS" | null;
  pipelineStatus: string | null;
  notes: string | null;

  createdAt: string | null;
  updatedAt: string | null;
}

/** Slimmer type returned by GET /parcels list */
export type ParcelListItem = Pick<
  Parcel,
  | "id" | "apn" | "city" | "state" | "county" | "zip"
  | "areaAcres" | "zoningCode" | "allowedUseCategory"
  | "estMaxLotCount" | "feasibilityScore" | "recommendation"
  | "isTaxDelinquent" | "hasCodeViolations" | "hasPreforeclosureFlag"
  | "isVacantLand" | "pipelineStatus" | "latitude" | "longitude"
>;

export interface PaginatedParcels {
  data: ParcelListItem[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}

export interface ParcelFilters {
  city?: string;
  county?: string;
  zip?: string;
  state?: string;
  min_acres?: number;
  max_acres?: number;
  zoning_codes?: string;
  allowed_use_categories?: string;
  min_est_max_lot_count?: number;
  max_est_max_lot_count?: number;
  feasibility_min?: number;
  feasibility_max?: number;
  recommendations?: string;
  distress?: string;
  page?: number;
  limit?: number;
}
