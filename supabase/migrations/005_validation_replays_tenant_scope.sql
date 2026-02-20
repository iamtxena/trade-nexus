-- GateV4 follow-up (#229): persist validation replay outcomes for auditability.

create table if not exists validation_replays (
  replay_id text primary key,
  baseline_id text not null references validation_baselines(id) on delete cascade,
  baseline_run_id text not null references validation_runs(run_id) on delete cascade,
  candidate_run_id text not null references validation_runs(run_id) on delete cascade,
  tenant_id text not null,
  user_id text not null,
  decision text not null check (decision in ('pass', 'conditional_pass', 'fail', 'unknown')),
  merge_blocked boolean not null,
  release_blocked boolean not null,
  merge_gate_status text not null check (merge_gate_status in ('pass', 'blocked')),
  release_gate_status text not null check (release_gate_status in ('pass', 'blocked')),
  baseline_decision text not null check (baseline_decision in ('pass', 'conditional_pass', 'fail')),
  candidate_decision text not null check (candidate_decision in ('pass', 'conditional_pass', 'fail')),
  metric_drift_delta_pct double precision not null check (metric_drift_delta_pct >= 0),
  metric_drift_threshold_pct double precision not null check (metric_drift_threshold_pct >= 0),
  threshold_breached boolean not null,
  reasons jsonb not null default '[]'::jsonb,
  summary text,
  created_at timestamptz not null default now()
);

create index if not exists idx_validation_replays_tenant_user_created
  on validation_replays (tenant_id, user_id, created_at desc);

create index if not exists idx_validation_replays_candidate_run
  on validation_replays (candidate_run_id, created_at desc);

alter table validation_replays enable row level security;

drop policy if exists "Users can manage own validation replays" on validation_replays;
create policy "Users can manage own validation replays" on validation_replays
  for all
  using (
    auth.jwt() ->> 'sub' = user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  )
  with check (
    auth.jwt() ->> 'sub' = user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  );
