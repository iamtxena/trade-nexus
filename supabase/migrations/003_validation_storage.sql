-- Validation Program storage schema v1.0
-- Tables: validation_runs, validation_reviews, validation_baselines, validation_regression_results
-- Supports: #226 (storage adapters), #229 (baseline replay + gates)

-- =============================================================
-- validation_runs — main validation workflow state
-- =============================================================
create table if not exists validation_runs (
  id uuid primary key default gen_random_uuid(),
  schema_version text not null default '1.0',
  user_id text not null,
  strategy_id text,
  backtest_id text,
  status text not null default 'pending'
    check (status in ('pending', 'running', 'passed', 'failed', 'error')),
  deterministic_result jsonb,
  agent_review_result jsonb,
  trader_review_status text not null default 'not_requested'
    check (trader_review_status in ('not_requested', 'requested', 'approved', 'rejected')),
  policy_decision jsonb,
  artifact_refs jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Auto-update updated_at on row modification
create or replace function update_validation_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create or replace trigger trg_validation_runs_updated_at
  before update on validation_runs
  for each row execute function update_validation_updated_at();

create index if not exists idx_validation_runs_user on validation_runs (user_id);
create index if not exists idx_validation_runs_strategy on validation_runs (strategy_id);
create index if not exists idx_validation_runs_user_created on validation_runs (user_id, created_at desc);

alter table validation_runs enable row level security;
-- Users can read own runs; mutations restricted to service role (governance table)
drop policy if exists "Users can read own rows" on validation_runs;
create policy "Users can read own rows" on validation_runs
  for select using (auth.jwt() ->> 'sub' = user_id);

-- =============================================================
-- validation_reviews — comments and verdicts
-- =============================================================
create table if not exists validation_reviews (
  id uuid primary key default gen_random_uuid(),
  schema_version text not null default '1.0',
  run_id uuid not null references validation_runs (id) on delete cascade,
  user_id text not null,
  reviewer_type text not null
    check (reviewer_type in ('human', 'agent')),
  verdict text
    check (verdict is null or verdict in ('pass', 'fail', 'conditional_pass')),
  comment text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_validation_reviews_run on validation_reviews (run_id);
create index if not exists idx_validation_reviews_user on validation_reviews (user_id);

alter table validation_reviews enable row level security;
-- Reviewers can read their own reviews; mutations via service role (governance table)
drop policy if exists "Reviewers can read own rows" on validation_reviews;
drop policy if exists "Reviewers can manage own rows" on validation_reviews;
create policy "Reviewers can read own rows" on validation_reviews
  for select using (auth.jwt() ->> 'sub' = user_id);
-- Run owners can read all reviews on their validation runs
drop policy if exists "Run owners can read reviews" on validation_reviews;
create policy "Run owners can read reviews" on validation_reviews
  for select using (
    exists (
      select 1 from validation_runs
      where validation_runs.id = validation_reviews.run_id
        and validation_runs.user_id = auth.jwt() ->> 'sub'
    )
  );

-- =============================================================
-- validation_baselines — approved baselines for regression
-- =============================================================
create table if not exists validation_baselines (
  id uuid primary key default gen_random_uuid(),
  schema_version text not null default '1.0',
  user_id text not null,
  strategy_id text not null,
  run_id uuid not null references validation_runs (id),
  baseline_data jsonb not null,
  promoted_at timestamptz not null default now(),
  promoted_by text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create index if not exists idx_validation_baselines_user on validation_baselines (user_id);
create index if not exists idx_validation_baselines_strategy on validation_baselines (strategy_id);
create unique index if not exists idx_validation_baselines_active on validation_baselines (user_id, strategy_id) where is_active = true;

alter table validation_baselines enable row level security;
-- Users can read own baselines; promotions restricted to service role (governance table)
drop policy if exists "Users can read own rows" on validation_baselines;
create policy "Users can read own rows" on validation_baselines
  for select using (auth.jwt() ->> 'sub' = user_id);

-- =============================================================
-- validation_regression_results — replay comparison results
-- =============================================================
create table if not exists validation_regression_results (
  id uuid primary key default gen_random_uuid(),
  schema_version text not null default '1.0',
  user_id text not null,
  baseline_id uuid not null references validation_baselines (id) on delete cascade,
  run_id uuid not null references validation_runs (id) on delete cascade,
  drift_metrics jsonb not null default '{}'::jsonb,
  policy_result text not null
    check (policy_result in ('pass', 'fail', 'warn')),
  gate_type text not null
    check (gate_type in ('merge', 'release')),
  created_at timestamptz not null default now()
);

create index if not exists idx_validation_regression_baseline on validation_regression_results (baseline_id);
create index if not exists idx_validation_regression_run on validation_regression_results (run_id);
create index if not exists idx_validation_regression_user on validation_regression_results (user_id);

alter table validation_regression_results enable row level security;
-- Users can read own results; mutations restricted to service role (governance table)
drop policy if exists "Users can read own rows" on validation_regression_results;
create policy "Users can read own rows" on validation_regression_results
  for select using (auth.jwt() ->> 'sub' = user_id);
