# Migration 009 Rollout Plan: CLI Auth Sessions

**Migration**: `009_cli_auth_sessions.sql`
**Rollback**: `009_cli_auth_sessions_rollback.sql`
**Author**: CloudOps Team
**Date**: 2026-03-02

## Overview

Adds 2 new tables (`cli_device_authorizations`, `cli_sessions`) to persist the platform team's device-flow CLI authentication state. Previously stored in-memory by `ValidationIdentityService`.

## Pre-Migration Checklist

- [ ] Verify current migration state (001-008 applied)
- [ ] Take database backup (see Backup section)
- [ ] Confirm no active long-running transactions
- [ ] Review migration SQL in PR
- [ ] Schedule change window (low-traffic period)

## Backup Procedure

### Option A: Supabase Dashboard
1. Go to Supabase Dashboard > Project Settings > Database
2. Click "Download backup" to get a full pg_dump

### Option B: CLI (if Supabase CLI is linked)
```bash
# Full database backup
supabase db dump -f backup_pre_009_$(date +%Y%m%d_%H%M%S).sql

# Data-only backup (no affected existing data for this migration)
supabase db dump --data-only -f backup_data_pre_009_$(date +%Y%m%d_%H%M%S).sql
```

### Option C: Direct pg_dump (production)
```bash
pg_dump "$DATABASE_URL" \
  --clean --if-exists \
  -f backup_pre_009_$(date +%Y%m%d_%H%M%S).sql
```

## Rollout Stages

### Stage 1: Dev (Local Supabase)

```bash
# Start local Supabase if not running
supabase start

# Apply migration
supabase db reset  # This applies all migrations fresh

# OR apply just this migration:
psql "$LOCAL_DB_URL" -f supabase/migrations/009_cli_auth_sessions.sql

# Verify
.ops/scripts/verify-migration-009.sh "$LOCAL_DB_URL"
```

**Gate**: All verification queries pass locally.

### Stage 2: Staging (if available)

> NOTE: Currently no staging environment exists (see .ops/evidence/supabase-environments.md).
> If a staging Supabase project is created before this migration ships,
> apply here first. Otherwise, proceed directly to production with extra care.

```bash
# Apply to staging
psql "$STAGING_DB_URL" -f supabase/migrations/009_cli_auth_sessions.sql

# Verify
.ops/scripts/verify-migration-009.sh "$STAGING_DB_URL"
```

**Gate**: All verification queries pass. Smoke test CLI auth endpoints.

### Stage 3: Production

```bash
# 1. Take backup FIRST
pg_dump "$PROD_DB_URL" --clean --if-exists -f backup_pre_009_$(date +%Y%m%d_%H%M%S).sql

# 2. Apply migration
psql "$PROD_DB_URL" -f supabase/migrations/009_cli_auth_sessions.sql

# 3. Run verification
.ops/scripts/verify-migration-009.sh "$PROD_DB_URL"

# 4. Smoke test
.ops/scripts/smoke-check-cli-auth.sh https://trade-nexus-backend.whitecliff-198cd26a.westeurope.azurecontainerapps.io
```

**Gate**: All verification queries pass. Smoke tests pass. No errors in Supabase logs.

## Verification Queries

Run after each stage to confirm migration applied correctly:

```sql
-- 1. Verify new tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('cli_device_authorizations', 'cli_sessions')
ORDER BY table_name;
-- Expected: 2 rows

-- 2. Verify RLS is enabled on both tables
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('cli_device_authorizations', 'cli_sessions')
ORDER BY tablename;
-- Expected: 2 rows, both with rowsecurity = true

-- 3. Verify policies exist
SELECT tablename, policyname, cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN ('cli_device_authorizations', 'cli_sessions')
ORDER BY tablename, policyname;
-- Expected: 1 on cli_device_authorizations, 2 on cli_sessions = 3 total

-- 4. Verify indexes
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('cli_device_authorizations', 'cli_sessions')
ORDER BY tablename, indexname;
-- Expected: 4 on cli_device_authorizations, 3 on cli_sessions = 7 total
-- (plus PK indexes = 9 total)

-- 5. Verify check constraint on status
SELECT conname, conrelid::regclass AS table_name
FROM pg_constraint
WHERE contype = 'c'
  AND conrelid::regclass::text = 'cli_device_authorizations'
ORDER BY conname;
-- Expected: 1 row (status check)

-- 6. Verify unique constraints on hash columns
SELECT indexname, indisunique
FROM pg_indexes i
JOIN pg_index pi ON pi.indexrelid = (schemaname || '.' || indexname)::regclass
WHERE schemaname = 'public'
  AND tablename = 'cli_device_authorizations'
  AND indexname LIKE '%hash%';
-- Expected: 2 rows, both unique
```

## Rollback Procedure

**Trigger conditions**:
- Migration fails mid-execution
- Verification queries show unexpected results
- Application errors post-migration
- RLS policies block legitimate backend access

### Rollback Steps

```bash
# 1. Apply rollback script
psql "$DB_URL" -f supabase/migrations/009_cli_auth_sessions_rollback.sql

# 2. Verify tables are dropped
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('cli_device_authorizations', 'cli_sessions');
-- Expected: 0 rows

# 3. Platform code falls back to in-memory state automatically
```

### If rollback script fails

Restore from backup:
```bash
psql "$DB_URL" -f backup_pre_009_YYYYMMDD_HHMMSS.sql
```

## Rollback Rehearsal

Before applying to production, rehearse the full cycle locally:

```bash
# 1. Start fresh
supabase db reset

# 2. Verify tables exist
psql "$LOCAL_DB_URL" -c "SELECT count(*) FROM information_schema.tables WHERE table_name = 'cli_device_authorizations'"

# 3. Apply rollback
psql "$LOCAL_DB_URL" -f supabase/migrations/009_cli_auth_sessions_rollback.sql

# 4. Verify tables gone
psql "$LOCAL_DB_URL" -c "SELECT count(*) FROM information_schema.tables WHERE table_name = 'cli_device_authorizations'"

# 5. Re-apply migration (proves idempotency of forward path)
psql "$LOCAL_DB_URL" -f supabase/migrations/009_cli_auth_sessions.sql

# 6. Final verification
.ops/scripts/verify-migration-009.sh "$LOCAL_DB_URL"
```

## Change Window

- **Preferred**: Weekday, 10:00-12:00 UTC (low-traffic for EU-based infra)
- **Duration**: ~3 minutes (DDL only, no data migration)
- **Downtime**: Zero (additive schema change, no table alterations)
- **Rollback time**: < 1 minute (DROP TABLE is fast)

## Post-Migration

- [ ] Record migration apply logs in `.ops/evidence/`
- [ ] Record rollback rehearsal output
- [ ] Update Supabase migration tracking (if CLI is linked)
- [ ] Set backend env vars (`CLI_AUTH_*`) via `az containerapp update`
- [ ] Run smoke check against production
- [ ] Monitor Supabase logs for 1 hour post-deploy
