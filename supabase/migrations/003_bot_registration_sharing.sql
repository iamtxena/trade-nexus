-- Migration 003: Bot Registration + Validation Sharing
-- Part of: Trade Nexus Validation Identity & Sharing Program v2
-- CloudOps ticket reference: infra/bot-registration-sharing
--
-- Non-negotiables enforced:
--   1) JSON is canonical validation artifact (results_json on validation_runs)
--   2) Bots self-register via invite-code OR partner-key path
--   3) No brand model in v1 — bots are user-owned (user_id FK)
--   4) Sharing is run-level only, invite by email only
--   5) Least-privilege RLS on all new tables
--
-- Also fixes: missing RLS on kb_* tables from migration 002

-- =============================================================
-- 1. bots — user-owned bot registrations
-- =============================================================
create table bots (
  id                  uuid primary key default gen_random_uuid(),
  user_id             text not null,
  name                text not null,
  description         text,
  status              text not null default 'active'
                      check (status in ('active', 'suspended', 'revoked')),
  registration_path   text not null
                      check (registration_path in ('invite_code', 'partner_key')),
  metadata            jsonb not null default '{}'::jsonb,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

create index idx_bots_user_id on bots (user_id);
create index idx_bots_status on bots (user_id, status);
create unique index idx_bots_user_name on bots (user_id, name);

alter table bots enable row level security;

-- Owner can do everything on their own bots
create policy "bot_owner_all" on bots
  for all using (auth.jwt() ->> 'sub' = user_id);

-- =============================================================
-- 2. bot_api_keys — API keys issued to bots
--    key_hash stores SHA-256; plaintext never stored
--    key_prefix stores first 8 chars for identification in UI
-- =============================================================
create table bot_api_keys (
  id          uuid primary key default gen_random_uuid(),
  bot_id      uuid not null references bots(id) on delete cascade,
  key_prefix  text not null,
  key_hash    text not null,
  scopes      jsonb not null default '["read"]'::jsonb,
  is_active   boolean not null default true,
  expires_at  timestamptz,
  created_at  timestamptz not null default now()
);

create index idx_bot_api_keys_bot_id on bot_api_keys (bot_id);
create index idx_bot_api_keys_hash on bot_api_keys (key_hash);
create index idx_bot_api_keys_prefix on bot_api_keys (key_prefix);

alter table bot_api_keys enable row level security;

-- Bot owner can manage keys via join to bots table
create policy "bot_key_owner_all" on bot_api_keys
  for all using (
    exists (
      select 1 from bots
      where bots.id = bot_api_keys.bot_id
        and bots.user_id = auth.jwt() ->> 'sub'
    )
  );

-- =============================================================
-- 3. validation_runs — canonical validation artifacts (JSON)
--    results_json is the canonical artifact per non-negotiable #1
--    bot_id is nullable (runs can be manual/human-initiated)
-- =============================================================
create table validation_runs (
  id              uuid primary key default gen_random_uuid(),
  user_id         text not null,
  bot_id          uuid references bots(id) on delete set null,
  strategy_id     uuid references strategies(id) on delete set null,
  status          text not null default 'pending'
                  check (status in ('pending', 'running', 'completed', 'failed', 'cancelled')),
  config_json     jsonb not null default '{}'::jsonb,
  results_json    jsonb,
  error_message   text,
  started_at      timestamptz,
  completed_at    timestamptz,
  created_at      timestamptz not null default now()
);

create index idx_validation_runs_user on validation_runs (user_id, created_at desc);
create index idx_validation_runs_strategy on validation_runs (strategy_id);
create index idx_validation_runs_status on validation_runs (user_id, status);

alter table validation_runs enable row level security;

-- Owner can manage their own runs
create policy "validation_run_owner_all" on validation_runs
  for all using (auth.jwt() ->> 'sub' = user_id);

-- =============================================================
-- 4. validation_run_shares — run-level sharing by email only
--    Per non-negotiable #4: sharing is run-level, invite by email
-- =============================================================
create table validation_run_shares (
  id                  uuid primary key default gen_random_uuid(),
  run_id              uuid not null references validation_runs(id) on delete cascade,
  shared_by_user_id   text not null,
  shared_with_email   text not null,
  access_level        text not null default 'view'
                      check (access_level in ('view', 'comment')),
  accepted_at         timestamptz,
  revoked_at          timestamptz,
  created_at          timestamptz not null default now()
);

create index idx_shares_run on validation_run_shares (run_id);
create index idx_shares_email on validation_run_shares (shared_with_email);
create index idx_shares_owner on validation_run_shares (shared_by_user_id);
create unique index idx_shares_unique on validation_run_shares (run_id, shared_with_email)
  where revoked_at is null;

alter table validation_run_shares enable row level security;

-- Share creator can manage shares, but only for runs they own
create policy "share_creator_all" on validation_run_shares
  for all using (
    auth.jwt() ->> 'sub' = shared_by_user_id
    and exists (
      select 1 from validation_runs
      where validation_runs.id = validation_run_shares.run_id
        and validation_runs.user_id = auth.jwt() ->> 'sub'
    )
  );

-- Share recipients can see shares addressed to them
create policy "share_recipient_select" on validation_run_shares
  for select using (auth.jwt() ->> 'email' = shared_with_email);

-- =============================================================
-- 4b. Deferred policy: shared recipients can SELECT runs shared with them
--     Created after validation_run_shares table exists to avoid 42P01
-- =============================================================
create policy "validation_run_shared_select" on validation_runs
  for select using (
    exists (
      select 1 from validation_run_shares
      where validation_run_shares.run_id = validation_runs.id
        and validation_run_shares.shared_with_email = auth.jwt() ->> 'email'
        and validation_run_shares.revoked_at is null
    )
  );

-- =============================================================
-- 5. Fix missing RLS on kb_* tables (from migration 002)
-- =============================================================

-- kb_patterns: service-role write, authenticated read only
alter table kb_patterns enable row level security;
create policy "kb_patterns_read" on kb_patterns
  for select using (auth.role() = 'authenticated');
create policy "kb_patterns_service_write" on kb_patterns
  for insert with check (auth.role() = 'service_role');
create policy "kb_patterns_service_update" on kb_patterns
  for update using (auth.role() = 'service_role');
create policy "kb_patterns_service_delete" on kb_patterns
  for delete using (auth.role() = 'service_role');

-- kb_market_regimes: service-role write, authenticated read only
alter table kb_market_regimes enable row level security;
create policy "kb_regimes_read" on kb_market_regimes
  for select using (auth.role() = 'authenticated');
create policy "kb_regimes_service_write" on kb_market_regimes
  for insert with check (auth.role() = 'service_role');
create policy "kb_regimes_service_update" on kb_market_regimes
  for update using (auth.role() = 'service_role');
create policy "kb_regimes_service_delete" on kb_market_regimes
  for delete using (auth.role() = 'service_role');

-- kb_lessons_learned: service-role write, authenticated read only
alter table kb_lessons_learned enable row level security;
create policy "kb_lessons_read" on kb_lessons_learned
  for select using (auth.role() = 'authenticated');
create policy "kb_lessons_service_write" on kb_lessons_learned
  for insert with check (auth.role() = 'service_role');
create policy "kb_lessons_service_update" on kb_lessons_learned
  for update using (auth.role() = 'service_role');
create policy "kb_lessons_service_delete" on kb_lessons_learned
  for delete using (auth.role() = 'service_role');

-- kb_macro_events: service-role write, authenticated read only
alter table kb_macro_events enable row level security;
create policy "kb_macro_events_read" on kb_macro_events
  for select using (auth.role() = 'authenticated');
create policy "kb_macro_events_service_write" on kb_macro_events
  for insert with check (auth.role() = 'service_role');
create policy "kb_macro_events_service_update" on kb_macro_events
  for update using (auth.role() = 'service_role');
create policy "kb_macro_events_service_delete" on kb_macro_events
  for delete using (auth.role() = 'service_role');

-- kb_correlations: service-role write, authenticated read only
alter table kb_correlations enable row level security;
create policy "kb_correlations_read" on kb_correlations
  for select using (auth.role() = 'authenticated');
create policy "kb_correlations_service_write" on kb_correlations
  for insert with check (auth.role() = 'service_role');
create policy "kb_correlations_service_update" on kb_correlations
  for update using (auth.role() = 'service_role');
create policy "kb_correlations_service_delete" on kb_correlations
  for delete using (auth.role() = 'service_role');
