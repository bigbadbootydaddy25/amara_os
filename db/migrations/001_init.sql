-- AMARA OS — PostgreSQL Schema
-- Migration 001: Core system of record

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─────────────────────────────────────────────
-- ENUMS
-- ─────────────────────────────────────────────

CREATE TYPE deal_strategy AS ENUM ('wholesale', 'flip', 'brrrr', 'subject_to', 'novation', 'unknown');
CREATE TYPE deal_status AS ENUM ('lead', 'analyzing', 'under_contract', 'closed_won', 'closed_lost', 'dead');
CREATE TYPE market_regime AS ENUM ('hot', 'neutral', 'cold', 'distressed');
CREATE TYPE ingestion_source AS ENUM ('manual', 'csv_upload', 'json_upload', 'openclaw_scrape', 'copy_paste');
CREATE TYPE exit_type AS ENUM ('assigned', 'double_close', 'listed', 'rented', 'held', 'lost');

-- ─────────────────────────────────────────────
-- PROPERTIES
-- ─────────────────────────────────────────────

CREATE TABLE properties (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Location
  address       TEXT NOT NULL,
  city          TEXT NOT NULL,
  state         CHAR(2) NOT NULL,
  zip           VARCHAR(10) NOT NULL,
  county        TEXT,
  apn           TEXT,
  latitude      NUMERIC(10,7),
  longitude     NUMERIC(10,7),

  -- Physical
  bedrooms      SMALLINT,
  bathrooms     NUMERIC(3,1),
  sqft          INTEGER,
  lot_sqft      INTEGER,
  year_built    SMALLINT,
  property_type TEXT,
  zoning        TEXT,

  -- Condition
  condition_grade  SMALLINT CHECK (condition_grade BETWEEN 1 AND 10),
  rehab_estimate   NUMERIC(12,2),

  -- Financials
  asking_price     NUMERIC(12,2),
  arv_estimate     NUMERIC(12,2),
  arv_low          NUMERIC(12,2),
  arv_high         NUMERIC(12,2),

  -- Distress signals
  tax_delinquent   BOOLEAN DEFAULT FALSE,
  bankruptcy       BOOLEAN DEFAULT FALSE,
  liens            BOOLEAN DEFAULT FALSE,
  vacant           BOOLEAN DEFAULT FALSE,
  pre_foreclosure  BOOLEAN DEFAULT FALSE,

  -- Metadata
  ingestion_source ingestion_source NOT NULL DEFAULT 'manual',
  raw_input        JSONB,
  notes            TEXT
);

CREATE INDEX idx_properties_zip ON properties(zip);
CREATE INDEX idx_properties_state_city ON properties(state, city);
CREATE INDEX idx_properties_created_at ON properties(created_at DESC);

-- ─────────────────────────────────────────────
-- DEALS
-- ─────────────────────────────────────────────

CREATE TABLE deals (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  property_id     UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  status          deal_status NOT NULL DEFAULT 'lead',
  strategy        deal_strategy NOT NULL DEFAULT 'unknown',

  -- Offer & contract
  mao             NUMERIC(12,2),
  offer_price     NUMERIC(12,2),
  contract_price  NUMERIC(12,2),
  assignment_fee  NUMERIC(12,2),

  -- Timelines
  lead_date       DATE,
  contract_date   DATE,
  close_date      DATE,
  days_to_close   INTEGER GENERATED ALWAYS AS (
    CASE WHEN close_date IS NOT NULL AND contract_date IS NOT NULL
    THEN close_date - contract_date ELSE NULL END
  ) STORED,

  -- Outcome (populated after close)
  exit_type       exit_type,
  actual_profit   NUMERIC(12,2),
  actual_roi      NUMERIC(7,4),
  buyer_id        UUID,

  notes           TEXT,
  metadata        JSONB
);

CREATE INDEX idx_deals_property_id ON deals(property_id);
CREATE INDEX idx_deals_status ON deals(status);
CREATE INDEX idx_deals_created_at ON deals(created_at DESC);

-- ─────────────────────────────────────────────
-- MIROFISH SIMULATIONS
-- ─────────────────────────────────────────────

CREATE TABLE mirofish_simulations (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  deal_id         UUID REFERENCES deals(id) ON DELETE SET NULL,
  property_id     UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,

  -- Feature vector snapshot
  features        JSONB NOT NULL,

  -- Scenario outputs
  conservative    JSONB NOT NULL,
  base            JSONB NOT NULL,
  aggressive      JSONB NOT NULL,

  -- Recommended output
  recommended_mao     NUMERIC(12,2),
  recommended_strategy deal_strategy,
  risk_score          NUMERIC(5,4) CHECK (risk_score BETWEEN 0 AND 1),
  confidence_score    NUMERIC(5,4) CHECK (confidence_score BETWEEN 0 AND 1),

  -- Model version that produced this simulation
  model_version   TEXT NOT NULL DEFAULT 'v1.0.0'
);

CREATE INDEX idx_simulations_property_id ON mirofish_simulations(property_id);
CREATE INDEX idx_simulations_created_at ON mirofish_simulations(created_at DESC);

-- ─────────────────────────────────────────────
-- MIROFISH MODEL WEIGHTS
-- ─────────────────────────────────────────────

CREATE TABLE mirofish_weights (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  version         TEXT NOT NULL UNIQUE,

  -- ZIP-level priors (stored as JSON map: { "77001": { ... } })
  zip_priors      JSONB NOT NULL DEFAULT '{}',

  -- Feature weights
  feature_weights JSONB NOT NULL,

  -- Learning metadata
  training_samples   INTEGER NOT NULL DEFAULT 0,
  last_trained_at    TIMESTAMPTZ,
  validation_mae     NUMERIC(10,4),
  notes              TEXT
);

-- Seed initial weights
INSERT INTO mirofish_weights (version, feature_weights) VALUES (
  'v1.0.0',
  '{
    "arv_discount_weight": 0.35,
    "rehab_risk_weight": 0.20,
    "liquidity_weight": 0.20,
    "buyer_demand_weight": 0.15,
    "distress_weight": 0.10
  }'
);

-- ─────────────────────────────────────────────
-- MARKET DATA
-- ─────────────────────────────────────────────

CREATE TABLE market_snapshots (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  snapshot_date   DATE NOT NULL,

  zip             VARCHAR(10),
  metro           TEXT,
  state           CHAR(2),

  -- Market signals
  median_arv          NUMERIC(12,2),
  avg_dom             NUMERIC(6,1),
  inventory_count     INTEGER,
  list_to_sale_ratio  NUMERIC(5,4),
  foreclosure_rate    NUMERIC(5,4),
  price_reduction_pct NUMERIC(5,4),

  regime              market_regime,
  ingestion_source    ingestion_source NOT NULL DEFAULT 'manual',
  raw_data            JSONB
);

CREATE INDEX idx_market_zip_date ON market_snapshots(zip, snapshot_date DESC);

-- ─────────────────────────────────────────────
-- BUYERS
-- ─────────────────────────────────────────────

CREATE TABLE buyers (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  name            TEXT NOT NULL,
  company         TEXT,
  email           TEXT,
  phone           TEXT,

  -- Preferences
  buyer_type      TEXT,    -- cash, hard_money, builder, landlord, owner_occupant
  target_zips     TEXT[],
  min_beds        SMALLINT,
  max_beds        SMALLINT,
  min_price       NUMERIC(12,2),
  max_price       NUMERIC(12,2),
  preferred_strategies TEXT[],

  -- Activity metrics
  deals_closed    INTEGER DEFAULT 0,
  avg_close_days  NUMERIC(5,1),
  reliability_score NUMERIC(5,4) CHECK (reliability_score BETWEEN 0 AND 1),

  notes           TEXT,
  metadata        JSONB
);

CREATE INDEX idx_buyers_target_zips ON buyers USING GIN(target_zips);

-- ─────────────────────────────────────────────
-- DEAL OUTCOMES (learning feed)
-- ─────────────────────────────────────────────

CREATE TABLE deal_outcomes (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  deal_id         UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
  property_id     UUID NOT NULL REFERENCES properties(id),

  -- Actuals vs predictions
  predicted_mao       NUMERIC(12,2),
  actual_contract     NUMERIC(12,2),
  predicted_arv       NUMERIC(12,2),
  actual_arv          NUMERIC(12,2),
  predicted_rehab     NUMERIC(12,2),
  actual_rehab        NUMERIC(12,2),
  predicted_dom       INTEGER,
  actual_dom          INTEGER,
  predicted_profit    NUMERIC(12,2),
  actual_profit       NUMERIC(12,2),

  -- Error signals for learning
  mao_error           NUMERIC(12,2) GENERATED ALWAYS AS (actual_contract - predicted_mao) STORED,
  arv_error           NUMERIC(12,2) GENERATED ALWAYS AS (actual_arv - predicted_arv) STORED,
  profit_error        NUMERIC(12,2) GENERATED ALWAYS AS (actual_profit - predicted_profit) STORED,

  -- Was prediction scenario correct?
  actual_scenario     TEXT,  -- conservative / base / aggressive
  model_version       TEXT,

  notes               TEXT
);

CREATE INDEX idx_outcomes_deal_id ON deal_outcomes(deal_id);
CREATE INDEX idx_outcomes_created_at ON deal_outcomes(created_at DESC);

-- ─────────────────────────────────────────────
-- INGESTION LOG
-- ─────────────────────────────────────────────

CREATE TABLE ingestion_log (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  source          ingestion_source NOT NULL,
  record_type     TEXT NOT NULL,  -- property, deal, market, buyer
  record_id       UUID,
  status          TEXT NOT NULL DEFAULT 'success',  -- success, error, skipped
  raw_input       JSONB,
  error_message   TEXT,
  processing_ms   INTEGER
);

CREATE INDEX idx_ingestion_log_created_at ON ingestion_log(created_at DESC);
CREATE INDEX idx_ingestion_log_source ON ingestion_log(source);

-- ─────────────────────────────────────────────
-- UPDATED_AT TRIGGER
-- ─────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_properties_updated_at
  BEFORE UPDATE ON properties
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_deals_updated_at
  BEFORE UPDATE ON deals
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_buyers_updated_at
  BEFORE UPDATE ON buyers
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
