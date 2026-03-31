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


-- ═══════════════════════════════════════════════════════════════════════════════
-- EXTENDED SCHEMA — Buyer Discovery, Learning, Entitlement, Orchestration
-- ═══════════════════════════════════════════════════════════════════════════════

-- ─── Buyers ───────────────────────────────────────────────────────────────────

create table if not exists buyers (
  buyer_id              text primary key,         -- BUY-XXXX
  name                  text not null,
  entity_name           text,
  email                 text,
  phone                 text,
  status                text default 'active',    -- active / paused / inactive
  strategy              text,                     -- flip / hold / both / land
  discovery_source      text,                     -- propstream / manual / referral
  activity_score        numeric default 0,        -- 0.0–1.0 computed from recent txns
  reliability_score     numeric default 0,        -- 0.0–1.0 (closes what they commit to)
  speed_score           numeric default 0,        -- 0.0–1.0 (days-to-close average)
  total_deals_12mo      integer default 0,
  total_deals_24mo      integer default 0,
  last_deal_date        date,
  vault_file            text,                     -- relative path to buyers/BUY-XXXX.md
  created_at            timestamp default now(),
  updated_at            timestamp default now()
);

create index if not exists idx_buyers_status on buyers(status);
create index if not exists idx_buyers_activity on buyers(activity_score);

-- ─── Buyer Transactions ───────────────────────────────────────────────────────

create table if not exists buyer_transactions (
  txn_id                text primary key,
  buyer_id              text references buyers(buyer_id),
  address               text not null,
  zip_code              text not null,
  purchase_date         date,
  purchase_price        numeric,
  property_type         text,                     -- SFR / MFR / land
  beds                  numeric,
  sqft                  integer,
  source                text,                     -- propstream / manual
  is_cash               boolean default true,
  days_to_close         integer,
  created_at            timestamp default now()
);

create index if not exists idx_txn_buyer on buyer_transactions(buyer_id);
create index if not exists idx_txn_zip on buyer_transactions(zip_code);
create index if not exists idx_txn_date on buyer_transactions(purchase_date);

-- ─── Buyer Buy Boxes ─────────────────────────────────────────────────────────

create table if not exists buyer_buyboxes (
  buybox_id             text primary key,
  buyer_id              text references buyers(buyer_id),
  zip_codes             text[],
  asset_types           text[],                   -- SFR / land / MFR
  min_price             numeric default 0,
  max_price             numeric,
  min_beds              integer default 0,
  max_repairs           numeric,                  -- null = no limit
  preferred_condition   text,                     -- cosmetic / light / medium / heavy
  min_sqft              integer,
  max_sqft              integer,
  inferred              boolean default false,    -- true if buy box was learned from txns
  inference_confidence  numeric default 0,        -- 0.0–1.0
  last_updated          timestamp default now(),
  notes                 text
);

create index if not exists idx_buybox_buyer on buyer_buyboxes(buyer_id);

-- ─── ZIP Liquidity ────────────────────────────────────────────────────────────

create table if not exists zip_liquidity (
  zip_code              text primary key,
  city                  text,
  state                 text,
  active_buyer_count    integer default 0,
  avg_days_to_close     numeric,
  median_buy_price      numeric,
  price_trend           text,                     -- rising / flat / declining
  demand_score          numeric default 0,        -- 0.0–1.0
  last_deal_date        date,
  deal_count_90d        integer default 0,
  deal_count_180d       integer default 0,
  updated_at            timestamp default now()
);

-- ─── Learning Events ─────────────────────────────────────────────────────────

create table if not exists learning_events (
  event_id              text primary key,
  event_type            text not null,            -- deal_closed / buyer_updated / market_shift /
                                                  --   mao_adjustment / no_buyer_signal
  source_id             text,                     -- deal_id / buyer_id / zip_code
  source_type           text,                     -- deal / buyer / market
  payload               jsonb,                    -- structured data about the event
  observation_id        text,                     -- links to observations/ vault
  processed             boolean default false,
  created_at            timestamp default now()
);

create index if not exists idx_learning_type on learning_events(event_type);
create index if not exists idx_learning_processed on learning_events(processed);

-- ─── Entity Updates ───────────────────────────────────────────────────────────

create table if not exists entity_updates (
  update_id             text primary key,
  entity_type           text not null,            -- buyer / market / zip / deal
  entity_id             text not null,
  field_name            text not null,
  old_value             text,
  new_value             text,
  reason                text,
  triggered_by          text,                     -- learning_event_id / manual / auto_matcher
  created_at            timestamp default now()
);

create index if not exists idx_entity_updates_entity on entity_updates(entity_id);

-- ─── Workflows ────────────────────────────────────────────────────────────────

create table if not exists workflows (
  workflow_id           text primary key,
  name                  text not null,            -- nightly_buyer_refresh / deal_hunt / etc.
  trigger_type          text not null,            -- scheduled / event
  schedule_cron         text,                     -- null for event-driven
  event_name            text,                     -- null for scheduled
  enabled               boolean default true,
  last_run_at           timestamp,
  last_run_status       text,                     -- success / failure / running
  consecutive_failures  integer default 0,
  created_at            timestamp default now()
);

-- ─── Workflow Jobs ────────────────────────────────────────────────────────────

create table if not exists workflow_jobs (
  job_id                text primary key,
  workflow_id           text references workflows(workflow_id),
  trigger_type          text,                     -- scheduled / event
  trigger_payload       jsonb,
  status                text default 'pending',   -- pending / running / success / failure / retrying
  started_at            timestamp,
  completed_at          timestamp,
  attempt_number        integer default 1,
  max_attempts          integer default 3,
  error_message         text,
  result_summary        text,
  created_at            timestamp default now()
);

create index if not exists idx_jobs_workflow on workflow_jobs(workflow_id);
create index if not exists idx_jobs_status on workflow_jobs(status);

-- ─── Workflow Events ─────────────────────────────────────────────────────────

create table if not exists workflow_events (
  event_id              text primary key,
  event_name            text not null,            -- new_property / offer_approved / offer_reply /
                                                  --   deal_closed / buyer_reply
  payload               jsonb,
  processed             boolean default false,
  job_id                text references workflow_jobs(job_id),
  created_at            timestamp default now()
);

create index if not exists idx_wf_events_name on workflow_events(event_name);
create index if not exists idx_wf_events_processed on workflow_events(processed);

-- ─── Land Entitlements ────────────────────────────────────────────────────────

create table if not exists land_entitlements (
  entitlement_id        text primary key,
  property_id           text references properties(property_id),
  deal_id               text,                     -- LAND-XXXX vault reference
  address               text not null,
  zip_code              text not null,
  county                text,

  -- Zoning
  current_zoning        text,
  target_zoning         text,
  zoning_change_needed  boolean default false,
  zoning_notes          text,

  -- Density
  max_density_per_acre  numeric,
  target_units          integer,
  density_bonus_eligible boolean default false,

  -- Plat Status
  plat_recorded         boolean default false,
  plat_phase            text,                     -- raw / preliminary / final / recorded
  plat_date             date,
  subdivision_name      text,

  -- Infrastructure
  water_available       boolean,
  sewer_available       boolean,
  road_access           boolean,
  utilities_distance_ft integer,

  -- Permit Pipeline
  pre_app_submitted     boolean default false,
  pre_app_date          date,
  preliminary_plat_submitted boolean default false,
  preliminary_plat_date date,
  final_plat_submitted  boolean default false,
  final_plat_date       date,
  permits_issued        boolean default false,

  -- Scores
  entitlement_score     numeric default 0,        -- 0.0–1.0 (how far along)
  builder_readiness_score numeric default 0,      -- 0.0–1.0 (ready for builder)
  risk_level            text default 'unknown',   -- low / medium / high / critical
  time_to_build_months  integer,

  created_at            timestamp default now(),
  updated_at            timestamp default now()
);

create index if not exists idx_entitlement_property on land_entitlements(property_id);
create index if not exists idx_entitlement_risk on land_entitlements(risk_level);

-- ─── Approval Status ─────────────────────────────────────────────────────────

create table if not exists approval_status (
  approval_id           text primary key,
  entitlement_id        text references land_entitlements(entitlement_id),
  property_id           text references properties(property_id),

  -- Stage tracking
  current_stage         text not null,            -- pre_app / preliminary_plat / final_plat /
                                                  --   permits / utilities / complete
  department            text,                     -- planning / engineering / fire / utilities
  last_activity_date    date,
  next_hearing_date     date,
  expected_stage_duration_days integer,

  -- Revision tracking
  revision_count        integer default 0,
  continuance_count     integer default 0,
  comment_rounds        integer default 0,

  -- Days in stage
  stage_entered_date    date,
  days_in_stage         integer,                  -- computed field, updated via trigger/app logic

  -- Backlog analysis
  backlog_score         numeric default 0,        -- 0.0–1.0 (1 = severe backlog)
  backlog_flag          boolean default false,    -- true if likely stuck
  likely_next_step      text,

  -- Notes
  notes                 text,
  last_contact          text,                     -- who was last contacted at the department

  created_at            timestamp default now(),
  updated_at            timestamp default now()
);

create index if not exists idx_approval_entitlement on approval_status(entitlement_id);
create index if not exists idx_approval_stage on approval_status(current_stage);
create index if not exists idx_approval_backlog on approval_status(backlog_flag);

-- ─── Offer Follow-Ups ─────────────────────────────────────────────────────────

create table if not exists offer_followups (
  followup_id           text primary key,
  offer_id              text references offer_queue(offer_id),
  scheduled_date        date not null,
  followup_number       integer default 1,        -- 1st / 2nd / 3rd contact
  channel               text default 'email',     -- email / phone / text
  status                text default 'pending',   -- pending / sent / replied / skipped
  message_template      text,
  sent_at               timestamp,
  reply_received_at     timestamp,
  reply_summary         text,
  created_at            timestamp default now()
);

create index if not exists idx_followup_offer on offer_followups(offer_id);
create index if not exists idx_followup_date on offer_followups(scheduled_date);
create index if not exists idx_followup_status on offer_followups(status);
