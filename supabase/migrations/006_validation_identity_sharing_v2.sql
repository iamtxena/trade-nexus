-- Validation Identity + Sharing Program v2 (Team A: Contract/Data)
-- Adds user-owned bot identity, hashed bot API keys, and run-level sharing invite primitives.
-- Canonical constraints:
-- 1) Bots are user-owned (no brand entity).
-- 2) Sharing scope is validation-run level only.
-- 3) Invites are email-only.
--
-- Rollback (manual, in reverse order):
-- 1) drop table if exists validation_run_shares;
-- 2) drop table if exists validation_invites;
-- 3) drop table if exists bot_api_keys;
-- 4) drop table if exists bots;
-- 5) alter table validation_runs drop column if exists owner_actor_type;
-- 6) alter table validation_runs drop column if exists owner_actor_id;
-- 7) alter table validation_runs drop column if exists owner_actor_metadata;
-- 8) alter table validation_runs drop column if exists owner_bot_id;
-- 9) alter table validation_runs drop column if exists owner_user_id;

create table if not exists bots (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null,
  owner_user_id text not null,
  name text not null,
  registration_path text not null
    check (registration_path in ('invite_code_trial', 'partner_bootstrap')),
  status text not null default 'active'
    check (status in ('active', 'suspended', 'revoked')),
  trial_expires_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  revoked_at timestamptz
);

create index if not exists idx_bots_owner_scope on bots (tenant_id, owner_user_id, created_at desc);
create index if not exists idx_bots_registration_path on bots (registration_path, created_at desc);

create table if not exists bot_api_keys (
  id uuid primary key default gen_random_uuid(),
  bot_id uuid not null references bots(id) on delete cascade,
  tenant_id text not null,
  owner_user_id text not null,
  key_prefix text not null,
  key_hash text not null,
  hash_algorithm text not null default 'sha256',
  status text not null default 'active'
    check (status in ('active', 'rotated', 'revoked')),
  created_at timestamptz not null default now(),
  last_used_at timestamptz,
  revoked_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  unique (key_hash)
);

create index if not exists idx_bot_api_keys_bot_created on bot_api_keys (bot_id, created_at desc);
create index if not exists idx_bot_api_keys_owner_scope on bot_api_keys (tenant_id, owner_user_id, created_at desc);
create index if not exists idx_bot_api_keys_status on bot_api_keys (status, created_at desc);

create table if not exists validation_invites (
  id uuid primary key default gen_random_uuid(),
  run_id text not null,
  tenant_id text not null,
  owner_user_id text not null,
  invited_email text not null,
  invited_by_actor_type text not null
    check (invited_by_actor_type in ('user', 'bot')),
  invited_by_actor_id text not null,
  invite_token_hash text not null unique,
  status text not null default 'pending'
    check (status in ('pending', 'accepted', 'revoked', 'expired')),
  message text,
  expires_at timestamptz,
  accepted_by_user_id text,
  accepted_at timestamptz,
  revoked_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_validation_invites_run_created on validation_invites (run_id, created_at desc);
create index if not exists idx_validation_invites_owner_scope on validation_invites (tenant_id, owner_user_id, created_at desc);
create index if not exists idx_validation_invites_email_run on validation_invites (run_id, lower(invited_email));
create unique index if not exists idx_validation_invites_pending_unique
  on validation_invites (run_id, lower(invited_email))
  where status = 'pending';

create table if not exists validation_run_shares (
  id uuid primary key default gen_random_uuid(),
  run_id text not null,
  tenant_id text not null,
  owner_user_id text not null,
  shared_with_email text not null,
  shared_with_user_id text,
  invite_id uuid references validation_invites(id) on delete set null,
  status text not null default 'active'
    check (status in ('active', 'revoked')),
  metadata jsonb not null default '{}'::jsonb,
  granted_at timestamptz not null default now(),
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_validation_run_shares_run_created
  on validation_run_shares (run_id, created_at desc);
create index if not exists idx_validation_run_shares_owner_scope
  on validation_run_shares (tenant_id, owner_user_id, created_at desc);
create index if not exists idx_validation_run_shares_shared_user
  on validation_run_shares (shared_with_user_id, created_at desc);
create unique index if not exists idx_validation_run_shares_active_email
  on validation_run_shares (run_id, lower(shared_with_email))
  where status = 'active';

alter table if exists validation_runs
  add column if not exists owner_actor_type text
    check (owner_actor_type in ('user', 'bot')),
  add column if not exists owner_actor_id text,
  add column if not exists owner_actor_metadata jsonb not null default '{}'::jsonb,
  add column if not exists owner_bot_id uuid references bots(id) on delete set null,
  add column if not exists owner_user_id text;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'validation_runs'
      and column_name = 'user_id'
  ) then
    execute $update$
      update validation_runs
      set owner_user_id = coalesce(owner_user_id, user_id)
      where owner_user_id is null
    $update$;
  end if;
end;
$$;

update validation_runs
set owner_actor_type = coalesce(owner_actor_type, 'user')
where owner_actor_type is null;

update validation_runs
set owner_actor_id = coalesce(owner_actor_id, owner_user_id)
where owner_actor_id is null;

create index if not exists idx_validation_runs_owner_actor
  on validation_runs (owner_actor_type, owner_actor_id);
create index if not exists idx_validation_runs_owner_user
  on validation_runs (owner_user_id, created_at desc);
create index if not exists idx_validation_runs_owner_bot
  on validation_runs (owner_bot_id, created_at desc);

alter table bots enable row level security;
alter table bot_api_keys enable row level security;
alter table validation_invites enable row level security;
alter table validation_run_shares enable row level security;

drop policy if exists "Users can manage own bots" on bots;
create policy "Users can manage own bots" on bots
  for all
  using (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  )
  with check (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  );

drop policy if exists "Users can manage own bot api keys" on bot_api_keys;
create policy "Users can manage own bot api keys" on bot_api_keys
  for all
  using (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  )
  with check (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  );

drop policy if exists "Users can manage own validation invites" on validation_invites;
create policy "Users can manage own validation invites" on validation_invites
  for all
  using (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  )
  with check (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  );

drop policy if exists "Users can manage own validation run shares" on validation_run_shares;
create policy "Users can manage own validation run shares" on validation_run_shares
  for all
  using (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  )
  with check (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  );

drop policy if exists "Users can read shared validation runs" on validation_run_shares;
create policy "Users can read shared validation runs" on validation_run_shares
  for select
  using (
    shared_with_user_id is not null
    and auth.jwt() ->> 'sub' = shared_with_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  );
