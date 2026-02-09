-- Trade Nexus: initial schema
-- Tables: strategies, agent_runs, predictions

-- =============================================================
-- strategies
-- =============================================================
create table strategies (
  id                uuid primary key default gen_random_uuid(),
  user_id           text not null,
  name              text not null,
  code              text not null,
  backtest_results  jsonb default null,
  is_active         boolean default false,
  created_at        timestamptz default now()
);

create index idx_strategies_user_id on strategies (user_id);

alter table strategies enable row level security;
create policy "Users can manage own rows" on strategies
  for all using (auth.jwt() ->> 'sub' = user_id);

-- =============================================================
-- agent_runs
-- =============================================================
create table agent_runs (
  id            uuid primary key default gen_random_uuid(),
  user_id       text not null,
  agent_type    text not null,
  input         jsonb not null,
  output        jsonb default null,
  status        text default 'pending'
                check (status in ('pending', 'running', 'completed', 'failed', 'idle')),
  created_at    timestamptz default now(),
  completed_at  timestamptz default null
);

create index idx_agent_runs_user_agent on agent_runs (user_id, agent_type);
create index idx_agent_runs_user_created on agent_runs (user_id, created_at desc);

alter table agent_runs enable row level security;
create policy "Users can manage own rows" on agent_runs
  for all using (auth.jwt() ->> 'sub' = user_id);

-- =============================================================
-- predictions
-- =============================================================
create table predictions (
  id              uuid primary key default gen_random_uuid(),
  user_id         text not null,
  symbol          text not null,
  prediction_type text not null
                  check (prediction_type in ('price', 'volatility', 'sentiment', 'trend')),
  value           jsonb not null,
  confidence      numeric not null
                  check (confidence >= 0 and confidence <= 100),
  created_at      timestamptz default now()
);

create index idx_predictions_user_symbol on predictions (user_id, symbol);
create index idx_predictions_user_created on predictions (user_id, created_at desc);

alter table predictions enable row level security;
create policy "Users can manage own rows" on predictions
  for all using (auth.jwt() ->> 'sub' = user_id);
