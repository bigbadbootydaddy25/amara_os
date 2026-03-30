-- AMARA OS — Auto Matcher Database Schema
-- All tables for the 10-stage pipeline

-- ─── Stage 1: Properties ─────────────────────────────────────────────────────

create table if not exists properties (
  property_id        text primary key,
  source             text not null,           -- zillow / xleads / propstream / propelio / csv / manual
  address            text not null,
  city               text,
  state              text,
  zip_code           text not null,
  county_name        text,
  parcel_id          text,
  property_type      text,                    -- SFR / MFR / land / commercial / mobile
  beds               numeric,
  baths              numeric,
  sqft               integer,
  lot_size           numeric,                 -- acres
  year_built         integer,
  list_price         numeric,
  dom                integer,                 -- days on market
  price_drops        integer default 0,       -- number of price reductions
  keywords           text[],                  -- extracted from description
  description        text,
  has_photos         boolean default false,
  bad_photos_flag    boolean default false,   -- manually or heuristically flagged
  created_at         timestamp default now(),
  updated_at         timestamp default now()
);

create index if not exists idx_properties_zip on properties(zip_code);
create index if not exists idx_properties_type on properties(property_type);
create index if not exists idx_properties_source on properties(source);

-- ─── Stage 2: Property Classifications ───────────────────────────────────────

create table if not exists property_classifications (
  property_id           text primary key references properties(property_id),
  classification        text not null,        -- sfr_wholesale / rental_hedge / infill_lot /
                                              --   land_subdivision / dead_paper / reject
  dead_paper_candidate  boolean default false,
  hedge_fund_fit        boolean default false,
  infill_candidate      boolean default false,
  reject_reason         text,
  classified_at         timestamp default now(),
  notes                 text
);

-- ─── Stage 3: Buyer Matches ───────────────────────────────────────────────────

create table if not exists property_matches (
  match_id              text primary key,
  property_id           text references properties(property_id),
  primary_buyer_id      text,                 -- links to buyers/ vault
  secondary_buyer_ids   text[],
  buyer_match_score     numeric,              -- 0.0 – 1.0
  builder_match_score   numeric,              -- land only
  comp_confidence       numeric,              -- 0.0 – 1.0
  final_score           numeric,              -- weighted composite
  approved              boolean default false,
  rejection_reason      text,
  created_at            timestamp default now()
);

create index if not exists idx_matches_property on property_matches(property_id);
create index if not exists idx_matches_approved on property_matches(approved);

-- ─── Stage 4–6: Underwriting ─────────────────────────────────────────────────

create table if not exists property_underwriting (
  underwriting_id       text primary key,
  property_id           text references properties(property_id),
  underwriting_type     text not null,        -- sfr / land

  -- SFR fields
  real_buyer_price      numeric,
  repairs_estimate      numeric,
  assignment_fee_target numeric,
  mao                   numeric,
  comp_count            integer,
  comp_sources          text[],               -- addresses used as comps

  -- Land fields
  gross_acres           numeric,
  net_factor            numeric default 0.75, -- usable land ratio
  net_developable_acres numeric,
  density               numeric,
  estimated_lots        integer,
  lot_to_home_ratio     numeric,
  median_new_home_price numeric,
  finished_lot_value    numeric,
  gross_lot_value       numeric,
  dev_cost_per_lot      numeric,
  horizontal_dev_cost   numeric,
  required_profit_margin numeric default 0.15,
  builder_profit        numeric,
  max_land_value        numeric,
  spread                numeric,

  -- Decision
  decision              text,                 -- go / negotiate / no_go
  decision_reason       text,
  created_at            timestamp default now()
);

create index if not exists idx_underwriting_property on property_underwriting(property_id);

-- ─── Stage 4: Comp Reads ─────────────────────────────────────────────────────

create table if not exists comp_reads (
  comp_id               text primary key,
  property_id           text references properties(property_id),
  comp_address          text not null,
  comp_zip              text,
  comp_sale_price       numeric,
  comp_sqft             integer,
  comp_beds             numeric,
  comp_baths            numeric,
  comp_sale_date        text,
  is_investor_exit      boolean default false,
  is_outlier            boolean default false,
  included_in_avg       boolean default true,
  created_at            timestamp default now()
);

create index if not exists idx_comps_property on comp_reads(property_id);

-- ─── Stage 7: Distress Scores ─────────────────────────────────────────────────

create table if not exists distress_scores (
  distress_id           text primary key,
  property_id           text references properties(property_id),
  property_type         text,                 -- sfr / land

  -- SFR signals
  dom_score             numeric default 0,    -- 0–1
  price_drop_score      numeric default 0,    -- 0–1
  keyword_score         numeric default 0,    -- 0–1
  bad_photos_score      numeric default 0,    -- 0–1
  vacancy_signal        boolean default false,
  inherited_signal      boolean default false,
  probate_signal        boolean default false,
  estate_signal         boolean default false,

  -- Land signals
  dead_paper_signal     boolean default false,
  ghost_street_signal   boolean default false,
  plat_phase_gap        boolean default false,
  builder_adjacency     boolean default false,
  ownership_weakness    boolean default false,

  -- Composite
  total_distress_score  numeric,              -- 0.0 – 1.0
  created_at            timestamp default now()
);

create index if not exists idx_distress_property on distress_scores(property_id);

-- ─── Stage 8–9: Final Scores + Approval ──────────────────────────────────────

create table if not exists match_scores (
  score_id              text primary key,
  property_id           text references properties(property_id),
  score_type            text not null,        -- sfr / land

  -- SFR component scores
  buyer_match_score     numeric default 0,    -- weight 0.30
  profit_score          numeric default 0,    -- weight 0.25
  distress_score        numeric default 0,    -- weight 0.20
  comp_confidence       numeric default 0,    -- weight 0.15
  speed_to_close_score  numeric default 0,    -- weight 0.10

  -- Land component scores
  builder_match_score   numeric default 0,    -- weight 0.30
  spread_score          numeric default 0,    -- weight 0.25
  dead_paper_score      numeric default 0,    -- weight 0.20
  location_score        numeric default 0,    -- weight 0.15
  ownership_score       numeric default 0,    -- weight 0.10

  -- Result
  final_score           numeric,
  gate_passed           boolean default false,
  gate_fail_reason      text,
  created_at            timestamp default now()
);

create index if not exists idx_scores_property on match_scores(property_id);
create index if not exists idx_scores_gate on match_scores(gate_passed);

-- ─── Stage 10: Offer Queue ────────────────────────────────────────────────────

create table if not exists offer_queue (
  offer_id              text primary key,
  property_id           text references properties(property_id),
  status                text default 'pending', -- pending / sent / accepted / rejected / expired
  primary_buyer_id      text,
  secondary_buyer_ids   text[],
  max_offer             numeric,               -- MAO for SFR, max land value for land
  target_fee            numeric,
  notes                 text,
  vault_deal_id         text,                  -- link to deals/DEAL-XXXX.md or land/LAND-XXXX.md
  queued_at             timestamp default now(),
  sent_at               timestamp,
  updated_at            timestamp default now()
);

create index if not exists idx_queue_status on offer_queue(status);
create index if not exists idx_queue_buyer on offer_queue(primary_buyer_id);

-- ─── Rejection Log ────────────────────────────────────────────────────────────

create table if not exists rejection_log (
  rejection_id          text primary key,
  property_id           text references properties(property_id),
  stage                 text,                  -- classification / buyer_lookup / underwriting /
                                               --   scoring / approval_gate
  reason                text not null,
  observation_logged    boolean default false, -- did this trigger an observation?
  created_at            timestamp default now()
);

create index if not exists idx_rejections_property on rejection_log(property_id);
create index if not exists idx_rejections_stage on rejection_log(stage);
