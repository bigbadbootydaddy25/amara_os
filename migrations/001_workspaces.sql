-- 001_workspaces.sql
-- Workspace registry, client registry, and deal pipeline (buyer-first doctrine).
-- Idempotent: safe to re-run against an existing database.

create extension if not exists pgcrypto;
create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- Workspaces
-- ---------------------------------------------------------------------------
-- Phase 1 ships exactly three isolated workspaces. Every data-carrying table
-- in AMARA OS must include a `workspace` column scoped to this set.

create table if not exists workspaces (
  id text primary key check (id in ('texhoma', 'acesn8s_dev', 'personal_investments')),
  label text not null,
  created_at timestamptz not null default now()
);

insert into workspaces (id, label) values
  ('texhoma', 'Texhoma Land Consultants'),
  ('acesn8s_dev', 'Aces N 8s Dev'),
  ('personal_investments', 'Personal Investments')
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- Client registry
-- ---------------------------------------------------------------------------
-- Ships with exactly one active client: Texhoma Land Consultants. The table
-- makes onboarding future landman clients a config/data operation, not a
-- code change -- but Phase 1 must not seed any client beyond the one below.

create table if not exists clients (
  id text primary key,
  name text not null,
  workspace text not null references workspaces (id),
  active boolean not null default true,
  created_at timestamptz not null default now()
);

insert into clients (id, name, workspace, active) values
  ('texhoma', 'Texhoma Land Consultants', 'texhoma', true)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- Deal pipeline (buyer-first doctrine)
-- ---------------------------------------------------------------------------
-- Hard rule: a deal can never reach the `offer` state without a confirmed
-- buyer price on file. This is enforced both here (defense in depth at the
-- data layer) and in application code (app/guards/pipeline.py).

create table if not exists deals (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  workspace text not null references workspaces (id),
  state text not null default 'lead' check (state in
    ('lead', 'under_contract', 'buyer_matching', 'offer', 'closed', 'dead')),
  confirmed_buyer_price numeric,
  metadata jsonb not null default '{}'
);

create index if not exists deals_workspace_idx on deals (workspace, state);

create or replace function enforce_buyer_first()
returns trigger as $$
begin
  if new.state = 'offer' and new.confirmed_buyer_price is null then
    raise exception 'buyer-first violation: deal % cannot enter state "offer" without confirmed_buyer_price', new.id;
  end if;
  new.updated_at := now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists deals_buyer_first on deals;
create trigger deals_buyer_first
  before insert or update on deals
  for each row execute function enforce_buyer_first();
