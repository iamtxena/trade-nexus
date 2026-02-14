-- Gate3 KB-01 canonical Knowledge Base schema v1.0

create table if not exists kb_patterns (
  id uuid primary key default gen_random_uuid(),
  schema_version text not null default '1.0',
  name text not null,
  pattern_type text not null,
  description text not null,
  suitable_regimes text[] not null default '{}',
  assets text[] not null default '{}',
  timeframes text[] not null default '{}',
  confidence_score numeric not null check (confidence_score >= 0 and confidence_score <= 1),
  source_ref text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists kb_market_regimes (
  id uuid primary key default gen_random_uuid(),
  schema_version text not null default '1.0',
  asset text not null,
  regime text not null,
  volatility text not null,
  indicators jsonb not null default '{}'::jsonb,
  start_at timestamptz not null default now(),
  end_at timestamptz,
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists kb_lessons_learned (
  id uuid primary key default gen_random_uuid(),
  schema_version text not null default '1.0',
  strategy_id text,
  backtest_id text,
  deployment_id text,
  category text not null,
  lesson text not null,
  tags text[] not null default '{}',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists kb_macro_events (
  id uuid primary key default gen_random_uuid(),
  schema_version text not null default '1.0',
  title text not null,
  summary text not null,
  impact text not null,
  assets text[] not null default '{}',
  occurred_at timestamptz not null,
  source_url text,
  created_at timestamptz not null default now()
);

create table if not exists kb_correlations (
  id uuid primary key default gen_random_uuid(),
  schema_version text not null default '1.0',
  source_asset text not null,
  target_asset text not null,
  correlation numeric not null check (correlation >= -1 and correlation <= 1),
  window text not null,
  computed_at timestamptz not null default now()
);

create index if not exists idx_kb_patterns_type on kb_patterns (pattern_type);
create index if not exists idx_kb_regimes_asset on kb_market_regimes (asset, start_at desc);
create index if not exists idx_kb_lessons_category on kb_lessons_learned (category, created_at desc);
create index if not exists idx_kb_events_impact on kb_macro_events (impact, occurred_at desc);
create index if not exists idx_kb_correlations_assets on kb_correlations (source_asset, target_asset);
