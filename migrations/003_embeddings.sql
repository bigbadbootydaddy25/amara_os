-- 003_embeddings.sql
-- pgvector similarity retrieval over the outcome log. This is the self-
-- learning loop for Phase 1: FOREMAN consults past outcomes (and any
-- corrections attached to them) before acting on a new, similar task.
-- Idempotent: safe to re-run against an existing database.

create extension if not exists vector;

-- ivfflat requires an estimate of row count to pick list size; 100 lists is
-- a reasonable default for early-stage data volumes and can be rebuilt later
-- as the table grows (`reindex index outcome_log_embedding_idx`).
create index if not exists outcome_log_embedding_idx
  on outcome_log using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- match_outcomes: returns the k outcome_log rows most similar to a query
-- embedding, scoped to a workspace and (optionally) a task_type.
create or replace function match_outcomes(
  query_embedding vector(768),
  match_workspace text,
  match_task_type text default null,
  match_count int default 5
)
returns table (
  id uuid,
  created_at timestamptz,
  workspace text,
  agent text,
  task_type text,
  input_summary text,
  action_taken text,
  outcome text,
  outcome_status text,
  correction text,
  similarity float
)
language sql stable
as $$
  select
    outcome_log.id,
    outcome_log.created_at,
    outcome_log.workspace,
    outcome_log.agent,
    outcome_log.task_type,
    outcome_log.input_summary,
    outcome_log.action_taken,
    outcome_log.outcome,
    outcome_log.outcome_status,
    outcome_log.correction,
    1 - (outcome_log.embedding <=> query_embedding) as similarity
  from outcome_log
  where outcome_log.workspace = match_workspace
    and outcome_log.embedding is not null
    and (match_task_type is null or outcome_log.task_type = match_task_type)
  order by outcome_log.embedding <=> query_embedding
  limit match_count;
$$;
