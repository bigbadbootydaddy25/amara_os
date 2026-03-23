-- ============================================================
-- Buyer Intelligence Engine — Database Schema
-- Truth-preserving: all buyer intelligence is derived from
-- recorded transactions. No speculative data is stored.
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- for fuzzy name deduplication

-- ─────────────────────────────────────────────────────────────────────────────
-- BUYER ENTITIES
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE buyer_entities (
  id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name                    TEXT NOT NULL,
  entity_type             TEXT NOT NULL DEFAULT 'unknown'
                            CHECK (entity_type IN (
                              'individual','llc','corporation','trust',
                              'partnership','institution','builder_developer','unknown'
                            )),

  -- Contact (optional enrichment — not used for verification)
  email                   TEXT,
  phone                   TEXT,
  website                 TEXT,

  -- Verification tier — COMPUTED, never manually assigned
  tier                    TEXT NOT NULL DEFAULT 'insufficient_data'
                            CHECK (tier IN (
                              'verified_active','verified_inactive',
                              'unverified','insufficient_data'
                            )),
  tier_computed_at        TIMESTAMPTZ,

  -- Verification flags (stored as JSONB for flexibility)
  verification_flags      JSONB NOT NULL DEFAULT '{}',

  -- All name variants seen in public records
  raw_name_variants       TEXT[] NOT NULL DEFAULT '{}',

  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_buyer_entities_name         ON buyer_entities USING gin(name gin_trgm_ops);
CREATE INDEX idx_buyer_entities_tier         ON buyer_entities(tier);
CREATE INDEX idx_buyer_entities_entity_type  ON buyer_entities(entity_type);
CREATE INDEX idx_buyer_entities_updated_at   ON buyer_entities(updated_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- TRANSACTIONS  (ground truth — recorded deed / MLS / public record)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE transactions (
  id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  buyer_entity_id     UUID NOT NULL REFERENCES buyer_entities(id) ON DELETE CASCADE,

  -- Recorded deed fields
  recorded_date       DATE NOT NULL,
  close_date          DATE,
  purchase_price      NUMERIC(14,2) NOT NULL CHECK (purchase_price >= 0),

  -- Location
  address             TEXT NOT NULL,
  city                TEXT NOT NULL,
  state               CHAR(2) NOT NULL,
  zip                 VARCHAR(10) NOT NULL,

  -- Property characteristics (nullable — only filled from actual records)
  property_type       TEXT NOT NULL DEFAULT 'unknown'
                        CHECK (property_type IN (
                          'sfr','mfr','condo','townhome','land',
                          'commercial','mobile_home','mixed_use','unknown'
                        )),
  sqft                INTEGER CHECK (sqft > 0),
  lot_size_sqft       INTEGER CHECK (lot_size_sqft > 0),
  bedrooms            SMALLINT CHECK (bedrooms >= 0),
  bathrooms           NUMERIC(3,1) CHECK (bathrooms >= 0),
  year_built          SMALLINT CHECK (year_built BETWEEN 1800 AND 2100),

  -- Source provenance
  source              TEXT NOT NULL,
  source_id           TEXT,
  verified            BOOLEAN NOT NULL DEFAULT FALSE,

  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE (source, source_id)  -- prevent duplicate imports
);

CREATE INDEX idx_transactions_buyer_entity_id ON transactions(buyer_entity_id);
CREATE INDEX idx_transactions_recorded_date   ON transactions(recorded_date);
CREATE INDEX idx_transactions_zip             ON transactions(zip);
CREATE INDEX idx_transactions_property_type   ON transactions(property_type);
CREATE INDEX idx_transactions_purchase_price  ON transactions(purchase_price);

-- ─────────────────────────────────────────────────────────────────────────────
-- BUY BOXES  (inferred — never manually authored)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE buy_boxes (
  id                              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  buyer_entity_id                 UUID NOT NULL UNIQUE REFERENCES buyer_entities(id) ON DELETE CASCADE,

  -- Price range (derived from actual purchase prices)
  price_min                       NUMERIC(14,2),
  price_max                       NUMERIC(14,2),
  price_avg                       NUMERIC(14,2),
  price_median                    NUMERIC(14,2),
  price_p25                       NUMERIC(14,2),
  price_p75                       NUMERIC(14,2),
  price_sample_count              INTEGER NOT NULL DEFAULT 0,

  -- Geographic preferences (JSON arrays of {zip, count, pct})
  preferred_zips                  JSONB NOT NULL DEFAULT '[]',
  preferred_states                TEXT[] NOT NULL DEFAULT '{}',
  preferred_cities                TEXT[] NOT NULL DEFAULT '{}',

  -- Property preferences
  property_types                  JSONB NOT NULL DEFAULT '[]',
  avg_sqft                        NUMERIC(10,2),
  sqft_min                        INTEGER,
  sqft_max                        INTEGER,
  avg_lot_size_sqft               NUMERIC(12,2),
  avg_year_built                  SMALLINT,

  -- Behavioral
  inferred_strategy               TEXT NOT NULL DEFAULT 'unknown'
                                    CHECK (inferred_strategy IN (
                                      'fix_and_flip','rental_portfolio','new_construction',
                                      'wholesale','land_banking','mixed_portfolio',
                                      'institutional_sfr','unknown'
                                    )),
  strategy_confidence             NUMERIC(4,3) CHECK (strategy_confidence BETWEEN 0 AND 1),
  avg_days_to_close               NUMERIC(6,1),
  acquisitions_per_year           NUMERIC(6,2),

  -- Provenance
  derived_from_transaction_count  INTEGER NOT NULL DEFAULT 0,
  last_derived_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_stale                        BOOLEAN NOT NULL DEFAULT FALSE,

  created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_buy_boxes_buyer_entity_id   ON buy_boxes(buyer_entity_id);
CREATE INDEX idx_buy_boxes_inferred_strategy ON buy_boxes(inferred_strategy);
CREATE INDEX idx_buy_boxes_price_avg         ON buy_boxes(price_avg);

-- ─────────────────────────────────────────────────────────────────────────────
-- ZIP LIQUIDITY  (heat map — computed from transaction records)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE zip_liquidity (
  id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  zip                         VARCHAR(10) NOT NULL,
  state                       CHAR(2) NOT NULL,
  city                        TEXT,

  -- Core counts
  total_transactions          INTEGER NOT NULL DEFAULT 0,
  unique_buyer_count          INTEGER NOT NULL DEFAULT 0,
  repeat_buyer_count          INTEGER NOT NULL DEFAULT 0,
  repeat_buyer_ratio          NUMERIC(5,4) NOT NULL DEFAULT 0,

  -- Velocity windows
  transactions_last_90d       INTEGER NOT NULL DEFAULT 0,
  transactions_last_180d      INTEGER NOT NULL DEFAULT 0,
  transactions_last_12mo      INTEGER NOT NULL DEFAULT 0,
  transactions_last_24mo      INTEGER NOT NULL DEFAULT 0,
  avg_transactions_per_month  NUMERIC(8,2),

  -- Scores (0–100)
  velocity_score              NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (velocity_score BETWEEN 0 AND 100),
  depth_score                 NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (depth_score BETWEEN 0 AND 100),
  consistency_score           NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (consistency_score BETWEEN 0 AND 100),
  liquidity_score             NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (liquidity_score BETWEEN 0 AND 100),
  liquidity_class             TEXT NOT NULL DEFAULT 'none'
                                CHECK (liquidity_class IN ('A','B','C','D','none')),
  exit_certainty              NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (exit_certainty BETWEEN 0 AND 100),

  -- Computation window
  analysis_window_start       DATE NOT NULL,
  analysis_window_end         DATE NOT NULL,
  computed_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE (zip, analysis_window_end)
);

CREATE INDEX idx_zip_liquidity_zip             ON zip_liquidity(zip);
CREATE INDEX idx_zip_liquidity_state           ON zip_liquidity(state);
CREATE INDEX idx_zip_liquidity_liquidity_class ON zip_liquidity(liquidity_class);
CREATE INDEX idx_zip_liquidity_exit_certainty  ON zip_liquidity(exit_certainty DESC);
CREATE INDEX idx_zip_liquidity_computed_at     ON zip_liquidity(computed_at);

-- ─────────────────────────────────────────────────────────────────────────────
-- MATERIALIZED VIEW: transaction_summary
-- Pre-aggregated buyer stats used by verification and buy-box inference
-- ─────────────────────────────────────────────────────────────────────────────

CREATE MATERIALIZED VIEW transaction_summary AS
SELECT
  t.buyer_entity_id,
  COUNT(*)                                          AS total_transactions,
  COUNT(*) FILTER (WHERE t.recorded_date >= NOW() - INTERVAL '12 months')
                                                    AS transactions_last_12mo,
  COUNT(*) FILTER (WHERE t.recorded_date >= NOW() - INTERVAL '24 months')
                                                    AS transactions_last_24mo,
  MIN(t.recorded_date)                              AS first_transaction_date,
  MAX(t.recorded_date)                              AS last_transaction_date,
  NOW()::DATE - MAX(t.recorded_date)                AS days_since_last_transaction,
  ROUND(AVG(t.purchase_price), 2)                   AS avg_purchase_price,
  MIN(t.purchase_price)                             AS min_purchase_price,
  MAX(t.purchase_price)                             AS max_purchase_price,
  SUM(t.purchase_price)                             AS total_volume,
  ARRAY_AGG(DISTINCT t.zip)                         AS zip_codes,
  ARRAY_AGG(DISTINCT t.property_type)               AS property_types,
  -- Acquisition pace: avg calendar days between consecutive transactions
  CASE WHEN COUNT(*) >= 2 THEN
    ROUND(
      EXTRACT(EPOCH FROM (MAX(t.recorded_date) - MIN(t.recorded_date)))
        / 86400.0
        / NULLIF(COUNT(*) - 1, 0),
      1
    )
  ELSE NULL END                                     AS avg_days_between_transactions
FROM transactions t
GROUP BY t.buyer_entity_id
WITH DATA;

CREATE UNIQUE INDEX idx_transaction_summary_buyer ON transaction_summary(buyer_entity_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- TRIGGERS: keep updated_at current
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_buyer_entities_updated_at
  BEFORE UPDATE ON buyer_entities
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_transactions_updated_at
  BEFORE UPDATE ON transactions
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_buy_boxes_updated_at
  BEFORE UPDATE ON buy_boxes
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_zip_liquidity_updated_at
  BEFORE UPDATE ON zip_liquidity
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
