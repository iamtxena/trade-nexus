-- CLI Auth Sessions: device-flow authorization + access sessions
-- Supports platform team's /v2/validation-cli-auth/ endpoints
-- Tables: cli_device_authorizations, cli_sessions

-- =============================================================
-- cli_device_authorizations
-- Maps to CliDeviceAuthorizationRecord in-memory state
-- =============================================================
create table cli_device_authorizations (
  id                       text primary key,  -- flow_id (clidev-XXXXXX)
  device_code_hash         text not null,      -- SHA-256 of device code
  user_code_hash           text not null,      -- SHA-256 of user code
  scopes                   jsonb not null,     -- ["validation:read","validation:write"]
  status                   text not null
                           check (status in ('pending', 'approved', 'consumed', 'expired')),
  verification_uri         text not null,      -- base verification URL
  polling_interval_seconds int not null default 5,
  approved_tenant_id       text,               -- filled on approval
  approved_user_id         text,               -- filled on approval
  created_by_user_id       text,               -- who approved
  approved_at              timestamptz,
  consumed_at              timestamptz,
  session_id               text,               -- linked session after consume
  created_at               timestamptz not null default now(),
  expires_at               timestamptz not null -- device code TTL
);

create unique index idx_cli_device_auth_device_code_hash
  on cli_device_authorizations (device_code_hash);
create unique index idx_cli_device_auth_user_code_hash
  on cli_device_authorizations (user_code_hash);
create index idx_cli_device_auth_status
  on cli_device_authorizations (status);
create index idx_cli_device_auth_expires_at
  on cli_device_authorizations (expires_at);

alter table cli_device_authorizations enable row level security;

-- Service-role only: backend manages these rows, not end users via JWT
create policy "Service role full access on cli_device_authorizations"
  on cli_device_authorizations
  for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

-- =============================================================
-- cli_sessions
-- Maps to CliAccessSessionRecord in-memory state
-- =============================================================
create table cli_sessions (
  session_id         text primary key,          -- clisess-XXXXXX
  tenant_id          text not null,
  user_id            text not null,             -- token owner
  created_by_user_id text not null,             -- who approved device auth
  token_hash         text not null,             -- PBKDF2-HMAC of secret
  token_salt         text not null,             -- 16 hex bytes
  scopes             jsonb not null,
  created_at         timestamptz not null default now(),
  expires_at         timestamptz not null,
  revoked_at         timestamptz,
  last_used_at       timestamptz
);

create index idx_cli_sessions_tenant_user
  on cli_sessions (tenant_id, user_id);
create index idx_cli_sessions_token_hash
  on cli_sessions (token_hash);
create index idx_cli_sessions_expires_at
  on cli_sessions (expires_at);

alter table cli_sessions enable row level security;

-- Owner can SELECT own sessions (for sessions list UI)
create policy "Users can view own cli sessions"
  on cli_sessions
  for select
  using (auth.jwt() ->> 'sub' = user_id);

-- Service-role for all mutations (create, update, delete)
create policy "Service role full access on cli_sessions"
  on cli_sessions
  for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');
