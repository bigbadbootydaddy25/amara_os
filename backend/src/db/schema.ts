import {
  bigserial,
  boolean,
  date,
  doublePrecision,
  integer,
  numeric,
  pgTable,
  text,
  timestamp,
  varchar,
} from "drizzle-orm/pg-core";
import { sql } from "drizzle-orm";

export const landParcels = pgTable("land_parcels", {
  id: bigserial("id", { mode: "number" }).primaryKey(),

  // Location
  apn:           varchar("apn", { length: 64 }),
  addressLine1:  text("address_line1"),
  city:          text("city"),
  state:         varchar("state", { length: 2 }),
  zip:           varchar("zip", { length: 10 }),
  county:        text("county"),
  jurisdiction:  text("jurisdiction"),
  latitude:      doublePrecision("latitude"),
  longitude:     doublePrecision("longitude"),
  areaSqft:      doublePrecision("area_sqft"),
  areaAcres:     doublePrecision("area_acres"),

  // Ownership
  ownerName:           text("owner_name"),
  ownerMailingAddress: text("owner_mailing_address"),
  lastSaleDate:        date("last_sale_date"),
  lastSalePrice:       numeric("last_sale_price", { precision: 14, scale: 2 }),
  assessedLandValue:   numeric("assessed_land_value", { precision: 14, scale: 2 }),
  assessedTotalValue:  numeric("assessed_total_value", { precision: 14, scale: 2 }),
  yearsOwned:          numeric("years_owned", { precision: 6, scale: 2 }),

  // Zoning
  zoningCode:         varchar("zoning_code", { length: 64 }),
  zoningDescription:  text("zoning_description"),
  allowedUseCategory: varchar("allowed_use_category", { length: 64 }),
  minLotSizeSqft:     doublePrecision("min_lot_size_sqft"),
  maxUnitsPerAcre:    doublePrecision("max_units_per_acre"),
  floorAreaRatio:     doublePrecision("floor_area_ratio"),
  maxHeightFt:        doublePrecision("max_height_ft"),
  frontSetbackFt:     doublePrecision("front_setback_ft"),
  sideSetbackFt:      doublePrecision("side_setback_ft"),
  rearSetbackFt:      doublePrecision("rear_setback_ft"),

  // Physical
  topographyClass:       varchar("topography_class", { length: 32 }),
  floodZoneCode:         varchar("flood_zone_code", { length: 32 }),
  hasEnvironmentalFlag:  boolean("has_environmental_flag"),
  accessType:            varchar("access_type", { length: 32 }),
  hasExistingStructure:  boolean("has_existing_structure"),
  existingUseType:       varchar("existing_use_type", { length: 64 }),
  existingBuildingSqft:  doublePrecision("existing_building_sqft"),

  // Utilities
  hasWater:  boolean("has_water"),
  hasSewer:  boolean("has_sewer"),
  hasPower:  boolean("has_power"),
  hasGas:    boolean("has_gas"),

  // Schools
  schoolDistrict:    text("school_district"),
  schoolScoreBucket: varchar("school_score_bucket", { length: 16 }),

  // Market
  nearbyNewBuildPricePerUnit:         numeric("nearby_new_build_price_per_unit", { precision: 12, scale: 2 }),
  nearbyResalePricePerSqft:           numeric("nearby_resale_price_per_sqft", { precision: 12, scale: 2 }),
  estimatedLandValueTotal:            numeric("estimated_land_value_total", { precision: 14, scale: 2 }),
  estimatedLandValuePerAcre:          numeric("estimated_land_value_per_acre", { precision: 14, scale: 2 }),
  estimatedLandValuePerPotentialLot:  numeric("estimated_land_value_per_potential_lot", { precision: 14, scale: 2 }),

  // Distress
  isTaxDelinquent:      boolean("is_tax_delinquent"),
  taxDelinquentAmount:  numeric("tax_delinquent_amount", { precision: 14, scale: 2 }),
  hasCodeViolations:    boolean("has_code_violations"),
  codeViolationCount:   integer("code_violation_count"),
  hasPreforeclosureFlag: boolean("has_preforeclosure_flag"),
  isVacantLand:         boolean("is_vacant_land"),
  isVacantStructure:    boolean("is_vacant_structure"),

  // Analysis
  targetProductType: varchar("target_product_type", { length: 64 }),
  estMaxLotCount:    integer("est_max_lot_count"),
  estMaxUnitCount:   integer("est_max_unit_count"),
  feasibilityScore:  integer("feasibility_score"),
  recommendation:    varchar("recommendation", { length: 16 }),
  pipelineStatus:    varchar("pipeline_status", { length: 32 }),
  notes:             text("notes"),

  // Timestamps
  createdAt: timestamp("created_at", { withTimezone: true }).default(sql`now()`),
  updatedAt: timestamp("updated_at", { withTimezone: true }).default(sql`now()`),
});

export type LandParcel = typeof landParcels.$inferSelect;
export type NewLandParcel = typeof landParcels.$inferInsert;
