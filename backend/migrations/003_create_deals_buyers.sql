-- Migration: 003_create_deals_buyers
-- Wholesale/acquisition deal flow: CSV-importable properties matched to buyer profiles

CREATE TABLE IF NOT EXISTS buyers (
  id              BIGSERIAL PRIMARY KEY,
  name            TEXT NOT NULL,
  email           TEXT,
  phone           TEXT,
  company         TEXT,

  -- Buy box criteria
  property_types  TEXT[],          -- {'SFR','MF','Land','Commercial'}
  beds_min        INTEGER,
  beds_max        INTEGER,
  baths_min       NUMERIC(3,1),
  baths_max       NUMERIC(3,1),
  sqft_min        INTEGER,
  sqft_max        INTEGER,
  price_min       NUMERIC(12,2),
  price_max       NUMERIC(12,2),
  arv_min         NUMERIC(12,2),
  arv_max         NUMERIC(12,2),
  max_rehab       NUMERIC(12,2),
  min_roi_pct     NUMERIC(5,2),    -- e.g. 15.00 = 15%
  zip_codes       TEXT[],          -- target zips
  states          TEXT[],          -- target states

  is_active       BOOLEAN DEFAULT true,
  notes           TEXT,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deals (
  id              BIGSERIAL PRIMARY KEY,

  -- Property info (CSV or manual)
  address         TEXT,
  city            TEXT,
  state           VARCHAR(2),
  zip             VARCHAR(10),
  county          TEXT,
  property_type   VARCHAR(32),     -- SFR | MF | Land | Commercial
  beds            INTEGER,
  baths           NUMERIC(3,1),
  sqft            INTEGER,
  lot_sqft        INTEGER,
  year_built      INTEGER,

  -- Financials
  asking_price    NUMERIC(12,2),
  arv             NUMERIC(12,2),   -- After Repair Value
  estimated_rehab NUMERIC(12,2),
  max_allowable_offer NUMERIC(12,2),

  -- Computed ratios
  roi_pct         NUMERIC(5,2),    -- (ARV - asking - rehab) / ARV * 100
  equity_pct      NUMERIC(5,2),    -- (ARV - asking) / ARV * 100

  -- Comps (stored as JSONB array of {address, price, sqft, distance})
  comps           JSONB,

  -- Source / import
  source          VARCHAR(64) DEFAULT 'MANUAL',
  import_batch_id VARCHAR(64),
  raw_csv_row     JSONB,

  -- Status
  status          VARCHAR(32) DEFAULT 'NEW',
  pipeline_stage  VARCHAR(32),     -- NEW | ANALYZING | MATCHED | SENT | UNDER_CONTRACT | CLOSED | DEAD
  assigned_to     TEXT,
  notes           TEXT,

  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deal_matches (
  id              BIGSERIAL PRIMARY KEY,
  deal_id         BIGINT NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
  buyer_id        BIGINT NOT NULL REFERENCES buyers(id) ON DELETE CASCADE,
  match_score     INTEGER NOT NULL,  -- 0-100
  match_reasons   JSONB,             -- [{field, weight, earned, note}]
  is_sent         BOOLEAN DEFAULT false,
  sent_at         TIMESTAMPTZ,
  created_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE(deal_id, buyer_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_deals_zip       ON deals(zip);
CREATE INDEX IF NOT EXISTS idx_deals_state     ON deals(state);
CREATE INDEX IF NOT EXISTS idx_deals_status    ON deals(status);
CREATE INDEX IF NOT EXISTS idx_deals_batch     ON deals(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_dm_deal         ON deal_matches(deal_id);
CREATE INDEX IF NOT EXISTS idx_dm_buyer        ON deal_matches(buyer_id);
CREATE INDEX IF NOT EXISTS idx_dm_score        ON deal_matches(match_score DESC);

DROP TRIGGER IF EXISTS trg_buyers_updated_at ON buyers;
CREATE TRIGGER trg_buyers_updated_at
  BEFORE UPDATE ON buyers FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_deals_updated_at ON deals;
CREATE TRIGGER trg_deals_updated_at
  BEFORE UPDATE ON deals FOR EACH ROW EXECUTE FUNCTION set_updated_at();
