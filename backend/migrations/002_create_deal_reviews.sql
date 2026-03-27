-- Migration: 002_create_deal_reviews
-- Amara OS autonomous deal review + document generation

CREATE TABLE IF NOT EXISTS deal_reviews (
  id                    BIGSERIAL PRIMARY KEY,
  parcel_id             BIGINT NOT NULL REFERENCES land_parcels(id) ON DELETE CASCADE,

  -- Amara's decision
  amara_decision        VARCHAR(32) NOT NULL,  -- APPROVED | REJECTED | NEEDS_MORE_INFO | PENDING
  confidence_score      NUMERIC(5,2),           -- 0.00–100.00
  amara_reasoning       TEXT,                   -- Amara's full reasoning chain

  -- Amara-generated documents (stored as text; front-end can render as markdown)
  loi_text              TEXT,
  loi_generated_at      TIMESTAMPTZ,

  owner_outreach_text   TEXT,
  outreach_generated_at TIMESTAMPTZ,

  negotiation_strategy  TEXT,
  negotiation_generated_at TIMESTAMPTZ,

  -- Deal lifecycle state (managed by Amara)
  lifecycle_status      VARCHAR(32) DEFAULT 'UNDER_REVIEW',
  -- UNDER_REVIEW → APPROVED → LOI_SENT → IN_NEGOTIATION → UNDER_CONTRACT → CLOSED | DEAD

  -- Pipeline metadata
  pipeline_run_id       VARCHAR(64),            -- which daily run surfaced this
  surfaced_at           TIMESTAMPTZ DEFAULT now(),
  reviewed_at           TIMESTAMPTZ,

  -- Human override
  human_override        VARCHAR(16),            -- APPROVED | REJECTED | null
  human_override_note   TEXT,
  overridden_at         TIMESTAMPTZ,
  overridden_by         TEXT,

  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dr_parcel_id ON deal_reviews(parcel_id);
CREATE INDEX IF NOT EXISTS idx_dr_decision       ON deal_reviews(amara_decision);
CREATE INDEX IF NOT EXISTS idx_dr_lifecycle      ON deal_reviews(lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_dr_pipeline_run   ON deal_reviews(pipeline_run_id);

CREATE TABLE IF NOT EXISTS pipeline_runs (
  id            BIGSERIAL PRIMARY KEY,
  run_id        VARCHAR(64) UNIQUE NOT NULL,
  triggered_by  VARCHAR(32) DEFAULT 'CRON',    -- CRON | MANUAL
  status        VARCHAR(32) DEFAULT 'RUNNING', -- RUNNING | COMPLETED | FAILED
  parcels_found INTEGER DEFAULT 0,
  parcels_sent_to_amara INTEGER DEFAULT 0,
  amara_approved INTEGER DEFAULT 0,
  amara_rejected INTEGER DEFAULT 0,
  error_message TEXT,
  started_at    TIMESTAMPTZ DEFAULT now(),
  completed_at  TIMESTAMPTZ
);

DROP TRIGGER IF EXISTS trg_dr_updated_at ON deal_reviews;
CREATE TRIGGER trg_dr_updated_at
  BEFORE UPDATE ON deal_reviews
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
