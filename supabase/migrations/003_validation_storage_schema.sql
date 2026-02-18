-- GateV4: validation storage metadata models (Supabase + blob refs + baselines)

create table if not exists validation_runs (
  run_id text primary key,
  request_id text not null,
  tenant_id text not null,
  user_id text not null,
  profile text not null check (profile in ('FAST', 'STANDARD', 'EXPERT')),
  status text not null check (status in ('queued', 'running', 'completed', 'failed')),
  final_decision text not null check (final_decision in ('pending', 'pass', 'conditional_pass', 'fail')),
  artifact_type text not null check (artifact_type in ('validation_run', 'validation_llm_snapshot')),
  artifact_schema_version text not null,
  artifact_ref text not null check (artifact_ref like 'blob://%'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists validation_review_states (
  run_id text primary key references validation_runs(run_id) on delete cascade,
  agent_status text not null check (agent_status in ('pass', 'conditional_pass', 'fail')),
  agent_summary text not null,
  findings_count integer not null default 0 check (findings_count >= 0),
  trader_required boolean not null default false,
  trader_status text not null check (trader_status in ('not_requested', 'requested', 'approved', 'rejected')),
  comments_count integer not null default 0 check (comments_count >= 0),
  updated_at timestamptz not null default now()
);

create table if not exists validation_blob_refs (
  id uuid primary key default gen_random_uuid(),
  run_id text not null references validation_runs(run_id) on delete cascade,
  kind text not null check (
    kind in (
      'strategy_code',
      'backtest_report',
      'trades',
      'execution_logs',
      'chart_payload',
      'render_html',
      'render_pdf'
    )
  ),
  ref text not null check (ref like 'blob://%'),
  content_type text not null,
  size_bytes bigint not null check (size_bytes >= 0),
  checksum_sha256 text not null check (checksum_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now(),
  unique (run_id, kind)
);

create table if not exists validation_baselines (
  id text primary key,
  run_id text not null references validation_runs(run_id) on delete cascade,
  tenant_id text not null,
  user_id text not null,
  name text not null,
  profile text not null check (profile in ('FAST', 'STANDARD', 'EXPERT')),
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists idx_validation_runs_tenant_user_created
  on validation_runs (tenant_id, user_id, created_at desc);

create index if not exists idx_validation_runs_profile_status
  on validation_runs (profile, status);

create index if not exists idx_validation_blob_refs_run
  on validation_blob_refs (run_id, created_at desc);

create index if not exists idx_validation_baselines_tenant_user_created
  on validation_baselines (tenant_id, user_id, created_at desc);

create unique index if not exists idx_validation_baselines_unique_name_per_scope
  on validation_baselines (tenant_id, user_id, name);
