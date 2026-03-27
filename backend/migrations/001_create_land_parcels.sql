-- Migration: 001_create_land_parcels
-- Run with: psql $DATABASE_URL -f migrations/001_create_land_parcels.sql

CREATE TABLE IF NOT EXISTS land_parcels (
  id                         BIGSERIAL PRIMARY KEY,
  apn                        VARCHAR(64),
  address_line1              TEXT,
  city                       TEXT,
  state                      VARCHAR(2),
  zip                        VARCHAR(10),
  county                     TEXT,
  jurisdiction               TEXT,
  latitude                   DOUBLE PRECISION,
  longitude                  DOUBLE PRECISION,
  area_sqft                  DOUBLE PRECISION,
  area_acres                 DOUBLE PRECISION,

  owner_name                 TEXT,
  owner_mailing_address      TEXT,
  last_sale_date             DATE,
  last_sale_price            NUMERIC(14,2),
  assessed_land_value        NUMERIC(14,2),
  assessed_total_value       NUMERIC(14,2),
  years_owned                NUMERIC(6,2),

  zoning_code                VARCHAR(64),
  zoning_description         TEXT,
  allowed_use_category       VARCHAR(64),
  min_lot_size_sqft          DOUBLE PRECISION,
  max_units_per_acre         DOUBLE PRECISION,
  floor_area_ratio           DOUBLE PRECISION,
  max_height_ft              DOUBLE PRECISION,
  front_setback_ft           DOUBLE PRECISION,
  side_setback_ft            DOUBLE PRECISION,
  rear_setback_ft            DOUBLE PRECISION,

  topography_class           VARCHAR(32),
  flood_zone_code            VARCHAR(32),
  has_environmental_flag     BOOLEAN,
  access_type                VARCHAR(32),
  has_existing_structure     BOOLEAN,
  existing_use_type          VARCHAR(64),
  existing_building_sqft     DOUBLE PRECISION,

  has_water                  BOOLEAN,
  has_sewer                  BOOLEAN,
  has_power                  BOOLEAN,
  has_gas                    BOOLEAN,
  school_district            TEXT,
  school_score_bucket        VARCHAR(16),

  nearby_new_build_price_per_unit NUMERIC(12,2),
  nearby_resale_price_per_sqft    NUMERIC(12,2),
  estimated_land_value_total      NUMERIC(14,2),
  estimated_land_value_per_acre   NUMERIC(14,2),
  estimated_land_value_per_potential_lot NUMERIC(14,2),

  is_tax_delinquent          BOOLEAN,
  tax_delinquent_amount      NUMERIC(14,2),
  has_code_violations        BOOLEAN,
  code_violation_count       INTEGER,
  has_preforeclosure_flag    BOOLEAN,
  is_vacant_land             BOOLEAN,
  is_vacant_structure        BOOLEAN,

  target_product_type        VARCHAR(64),
  est_max_lot_count          INTEGER,
  est_max_unit_count         INTEGER,
  feasibility_score          INTEGER,
  recommendation             VARCHAR(16),
  pipeline_status            VARCHAR(32),
  notes                      TEXT,

  created_at                 TIMESTAMPTZ DEFAULT now(),
  updated_at                 TIMESTAMPTZ DEFAULT now()
);

-- Indexes for common filter patterns
CREATE INDEX IF NOT EXISTS idx_lp_city_state   ON land_parcels(city, state);
CREATE INDEX IF NOT EXISTS idx_lp_county       ON land_parcels(county);
CREATE INDEX IF NOT EXISTS idx_lp_zip          ON land_parcels(zip);
CREATE INDEX IF NOT EXISTS idx_lp_zoning       ON land_parcels(zoning_code);
CREATE INDEX IF NOT EXISTS idx_lp_feasibility  ON land_parcels(feasibility_score);
CREATE INDEX IF NOT EXISTS idx_lp_recommendation ON land_parcels(recommendation);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_lp_updated_at ON land_parcels;
CREATE TRIGGER trg_lp_updated_at
  BEFORE UPDATE ON land_parcels
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
