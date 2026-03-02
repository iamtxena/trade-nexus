-- Rollback for 009_cli_auth_sessions.sql
-- Drops CLI auth tables in reverse dependency order

-- =============================================================
-- cli_sessions (drop policies, indexes, table)
-- =============================================================
drop policy if exists "Users can view own cli sessions" on cli_sessions;
drop policy if exists "Service role full access on cli_sessions" on cli_sessions;

drop index if exists idx_cli_sessions_tenant_user;
drop index if exists idx_cli_sessions_token_hash;
drop index if exists idx_cli_sessions_expires_at;

drop table if exists cli_sessions;

-- =============================================================
-- cli_device_authorizations (drop policies, indexes, table)
-- =============================================================
drop policy if exists "Service role full access on cli_device_authorizations" on cli_device_authorizations;

drop index if exists idx_cli_device_auth_device_code_hash;
drop index if exists idx_cli_device_auth_user_code_hash;
drop index if exists idx_cli_device_auth_status;
drop index if exists idx_cli_device_auth_expires_at;

drop table if exists cli_device_authorizations;
