-- 002_outcome_log.sql
-- The Outcome Log: the memory substrate that makes AMARA self-learning
-- possible later (REFLECT, Phase 3). Phase 1 only writes and retrieves.
-- Idempotent: safe to re-run against an existing database.

create table if not exists outcome_log (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  workspace text not null references workspaces (id),
  agent text not null,              -- 'foreman' in phase 1
  task_type text not null,          -- e.g. 'deal_score','deed_read','draft'
  input_summary text not null,      -- short human-readable summary
  action_taken text not null,       -- what the system did
  outcome text,                     -- filled later: what actually happened
  outcome_status text not null default 'pending' check (outcome_status in
    ('pending', 'success', 'partial', 'failure', 'corrected')),
  correction text,                  -- Scott's correction if any
  scored_by text check (scored_by in ('nova')),
  metadata jsonb not null default '{}',
  embedding vector(768)             -- for pgvector retrieval, see 003_embeddings.sql
);

create index if not exists outcome_log_workspace_type_idx
  on outcome_log (workspace, task_type, created_at desc);
