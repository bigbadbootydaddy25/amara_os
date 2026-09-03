-- Title Runsheet App — Postgres schema
--
-- One "project" = one title run (a seller package + the recorded instruments
-- pulled to abstract it), scoped to a survey tract (Section/Block/Township,
-- County, State). Everything else hangs off project_id.

create extension if not exists "pgcrypto";

create table if not exists projects (
  id                              uuid primary key default gen_random_uuid(),
  name                            text not null,
  state                           text not null default 'TX',
  county                          text not null,
  survey_section                  text,
  survey_block                    text,
  survey_township                 text,   -- e.g. "T1S"
  survey_abstract_no              text,
  legal_description                text,
  dropbox_seller_package_path     text not null,
  dropbox_recorded_instruments_path text not null,
  dropbox_runsheet_export_path    text,
  dropbox_report_export_path      text,
  status                          text not null default 'new'
                                    check (status in ('new','intake','retrieving','abstracting','curative','exporting','complete','error')),
  created_at                      timestamptz not null default now(),
  updated_at                      timestamptz not null default now()
);

create table if not exists documents (
  id               uuid primary key default gen_random_uuid(),
  project_id       uuid not null references projects(id) on delete cascade,
  source           text not null check (source in ('seller_package','recorded_instrument','portal_download')),
  dropbox_path     text not null,
  dropbox_rev      text,
  file_name        text not null,
  content_hash     text,
  mime_type        text,
  ocr_text         text,
  status           text not null default 'new'
                     check (status in ('new','processing','processed','error','skipped')),
  error_message    text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  unique (project_id, dropbox_path)
);

create table if not exists instruments (
  id                  uuid primary key default gen_random_uuid(),
  project_id          uuid not null references projects(id) on delete cascade,
  document_id         uuid references documents(id) on delete set null,
  instrument_type     text,     -- e.g. Deed, Oil & Gas Lease, Assignment, Release, Affidavit of Heirship, Probate
  grantors             text[] not null default '{}',
  grantees             text[] not null default '{}',
  execution_date       date,
  recording_date       date,
  county               text,
  state                text default 'TX',
  volume               text,
  page                 text,
  instrument_number    text,
  legal_description    text,
  net_mineral_acres    numeric,
  royalty_reserved     text,
  notes                text,
  raw_extraction       jsonb not null default '{}'::jsonb,
  confidence           numeric,   -- 0-1, extraction confidence from the abstracting agent
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);

create index if not exists idx_instruments_project on instruments(project_id);
create index if not exists idx_instruments_recording_date on instruments(project_id, recording_date);

create table if not exists runsheet_entries (
  id             uuid primary key default gen_random_uuid(),
  project_id     uuid not null references projects(id) on delete cascade,
  instrument_id  uuid not null references instruments(id) on delete cascade,
  sequence_no    integer not null,
  entry_summary  text,
  created_at     timestamptz not null default now(),
  unique (project_id, sequence_no)
);

create table if not exists curative_items (
  id             uuid primary key default gen_random_uuid(),
  project_id     uuid not null references projects(id) on delete cascade,
  instrument_id  uuid references instruments(id) on delete set null,
  severity       text not null default 'warning' check (severity in ('info','warning','critical')),
  category       text not null,   -- e.g. gap_in_chain, missing_release, name_variance, unrecorded_conveyance
  description    text not null,
  status         text not null default 'open' check (status in ('open','resolved','waived')),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create table if not exists portal_search_results (
  id                 uuid primary key default gen_random_uuid(),
  project_id         uuid not null references projects(id) on delete cascade,
  portal             text not null,  -- 'texasfile' | 'county_clerk' | other configured portal
  instrument_number  text,
  instrument_type    text,
  recording_date     date,
  grantor            text,
  grantee            text,
  download_status    text not null default 'pending' check (download_status in ('pending','downloaded','failed','skipped')),
  dropbox_path       text,
  error_message      text,
  created_at         timestamptz not null default now()
);

create table if not exists agent_runs (
  id             uuid primary key default gen_random_uuid(),
  project_id     uuid not null references projects(id) on delete cascade,
  agent_name     text not null check (agent_name in
                   ('intake','instrument_retrieval','abstracting','curative_qc','runsheet_export','report')),
  status         text not null default 'running' check (status in ('running','succeeded','failed')),
  started_at     timestamptz not null default now(),
  finished_at    timestamptz,
  summary        text,
  error_message  text,
  metadata       jsonb not null default '{}'::jsonb
);

create index if not exists idx_agent_runs_project on agent_runs(project_id, agent_name, started_at desc);
