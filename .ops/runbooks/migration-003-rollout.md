# Migration 003 Rollout Plan: Bot Registration + Validation Sharing

**Migration**: `003_bot_registration_sharing.sql`
**Rollback**: `003_bot_registration_sharing_rollback.sql`
**Author**: CloudOps Team
**Date**: 2026-02-21

## Overview

Adds 4 new tables (`bots`, `bot_api_keys`, `validation_runs`, `validation_run_shares`) and fixes missing RLS on 5 `kb_*` tables from migration 002.

## Pre-Migration Checklist

- [ ] Verify current migration state (001, 002 applied)
- [ ] Take database backup (see Backup section)
- [ ] Confirm no active long-running transactions
- [ ] Review migration SQL in PR
- [ ] Schedule change window (low-traffic period)

## Backup Procedure

### Option A: Supabase Dashboard
1. Go to Supabase Dashboard → Project Settings → Database
2. Click "Download backup" to get a full pg_dump

### Option B: CLI (if Supabase CLI is linked)
```bash
# Full database backup
supabase db dump -f backup_pre_003_$(date +%Y%m%d_%H%M%S).sql

# Data-only backup of affected tables (kb_* tables have existing data)
supabase db dump --data-only -f backup_data_pre_003_$(date +%Y%m%d_%H%M%S).sql
```

### Option C: Direct pg_dump (production)
```bash
pg_dump "$DATABASE_URL" \
  --clean --if-exists \
  -f backup_pre_003_$(date +%Y%m%d_%H%M%S).sql
```

## Rollout Stages

### Stage 1: Dev (Local Supabase)

```bash
# Start local Supabase if not running
supabase start

# Apply migration
supabase db reset  # This applies all migrations fresh

# OR apply just this migration:
psql "$LOCAL_DB_URL" -f supabase/migrations/003_bot_registration_sharing.sql

# Verify (see Verification section)
```

**Gate**: All verification queries pass locally.

### Stage 2: Staging (if available)

> NOTE: Currently no staging environment exists (see .ops/evidence/supabase-environments.md).
> If a staging Supabase project is created before this migration ships,
> apply here first. Otherwise, proceed directly to production with extra care.

```bash
# Apply to staging
psql "$STAGING_DB_URL" -f supabase/migrations/003_bot_registration_sharing.sql
```

**Gate**: All verification queries pass. Smoke test bot registration + sharing API endpoints.

### Stage 3: Production

```bash
# 1. Take backup FIRST
pg_dump "$PROD_DB_URL" --clean --if-exists -f backup_pre_003_$(date +%Y%m%d_%H%M%S).sql

# 2. Apply migration
psql "$PROD_DB_URL" -f supabase/migrations/003_bot_registration_sharing.sql

# 3. Run verification queries (see below)

# 4. Smoke test (see below)
```

**Gate**: All verification queries pass. Smoke tests pass. No errors in Supabase logs.

## Verification Queries

Run after each stage to confirm migration applied correctly:

```sql
-- 1. Verify new tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('bots', 'bot_api_keys', 'validation_runs', 'validation_run_shares')
ORDER BY table_name;
-- Expected: 4 rows

-- 2. Verify RLS is enabled on ALL tables
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'bots', 'bot_api_keys', 'validation_runs', 'validation_run_shares',
    'kb_patterns', 'kb_market_regimes', 'kb_lessons_learned',
    'kb_macro_events', 'kb_correlations'
  )
ORDER BY tablename;
-- Expected: 9 rows, all with rowsecurity = true

-- 3. Verify policies exist
SELECT tablename, policyname, cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN (
    'bots', 'bot_api_keys', 'validation_runs', 'validation_run_shares',
    'kb_patterns', 'kb_market_regimes', 'kb_lessons_learned',
    'kb_macro_events', 'kb_correlations'
  )
ORDER BY tablename, policyname;
-- Expected: 2 on bots, 1 on bot_api_keys, 2 on validation_runs,
--           2 on validation_run_shares, 4 each on 5 kb_* tables = 27 total

-- 4. Verify indexes
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('bots', 'bot_api_keys', 'validation_runs', 'validation_run_shares')
ORDER BY tablename, indexname;

-- 5. Verify check constraints
SELECT conname, conrelid::regclass AS table_name
FROM pg_constraint
WHERE contype = 'c'
  AND conrelid::regclass::text IN ('bots', 'validation_runs', 'validation_run_shares')
ORDER BY table_name, conname;

-- 6. Verify FK relationships
SELECT conname, conrelid::regclass AS table_name, confrelid::regclass AS referenced
FROM pg_constraint
WHERE contype = 'f'
  AND conrelid::regclass::text IN ('bot_api_keys', 'validation_runs', 'validation_run_shares')
ORDER BY table_name;
```

## Rollback Procedure

**Trigger conditions**:
- Migration fails mid-execution
- Verification queries show unexpected results
- Application errors post-migration
- RLS policies block legitimate access

### Rollback Steps

```bash
# 1. Apply rollback script
psql "$DB_URL" -f supabase/migrations/003_bot_registration_sharing_rollback.sql

# 2. Verify tables are dropped
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('bots', 'bot_api_keys', 'validation_runs', 'validation_run_shares');
-- Expected: 0 rows

# 3. Verify KB tables RLS is disabled (back to pre-003 state)
SELECT tablename, rowsecurity FROM pg_tables
WHERE schemaname = 'public' AND tablename LIKE 'kb_%';
-- Expected: all false (WARNING: this re-opens the security gap)
```

### If rollback script fails

Restore from backup:
```bash
psql "$DB_URL" -f backup_pre_003_YYYYMMDD_HHMMSS.sql
```

## Rollback Rehearsal

Before applying to production, rehearse the full cycle locally:

```bash
# 1. Start fresh
supabase db reset

# 2. Verify tables exist
psql "$LOCAL_DB_URL" -c "SELECT count(*) FROM information_schema.tables WHERE table_name = 'bots'"

# 3. Apply rollback
psql "$LOCAL_DB_URL" -f supabase/migrations/003_bot_registration_sharing_rollback.sql

# 4. Verify tables gone
psql "$LOCAL_DB_URL" -c "SELECT count(*) FROM information_schema.tables WHERE table_name = 'bots'"

# 5. Re-apply migration (proves idempotency of forward path)
psql "$LOCAL_DB_URL" -f supabase/migrations/003_bot_registration_sharing.sql

# 6. Final verification
# Run all verification queries from above
```

## Change Window

- **Preferred**: Weekday, 10:00-12:00 UTC (low-traffic for EU-based infra)
- **Duration**: ~5 minutes (DDL only, no data migration)
- **Downtime**: Zero (additive schema change, no table alterations)
- **Rollback time**: < 1 minute (DROP TABLE is fast)

## Post-Migration

- [ ] Record migration apply logs in `.ops/evidence/`
- [ ] Record rollback rehearsal output
- [ ] Update Supabase migration tracking (if CLI is linked)
- [ ] Notify product team migration is complete
- [ ] Monitor Supabase logs for 1 hour post-deploy
