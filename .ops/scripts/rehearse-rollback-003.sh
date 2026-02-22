#!/usr/bin/env bash
# rehearse-rollback-003.sh — Full forward/rollback/re-apply cycle for migration 003
# Usage: ./rehearse-rollback-003.sh <DATABASE_URL>
# Requires: psql, the migration files, and verify-migration-003.sh
set -euo pipefail

DB_URL="${1:?Usage: rehearse-rollback-003.sh <DATABASE_URL>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MIGRATION_DIR="$(cd "$SCRIPT_DIR/../../supabase/migrations" && pwd)"

echo "=========================================="
echo "Rollback Rehearsal — Migration 003"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=========================================="

echo ""
echo "--- Step 1: Apply migration 003 ---"
psql "$DB_URL" -f "$MIGRATION_DIR/003_bot_registration_sharing.sql" 2>&1
echo "Migration applied."

echo ""
echo "--- Step 2: Verify forward migration ---"
"$SCRIPT_DIR/verify-migration-003.sh" "$DB_URL" || {
  echo "ERROR: Forward migration verification failed. Aborting rehearsal."
  exit 1
}

echo ""
echo "--- Step 3: Apply rollback ---"
psql "$DB_URL" -f "$MIGRATION_DIR/003_bot_registration_sharing_rollback.sql" 2>&1
echo "Rollback applied."

echo ""
echo "--- Step 4: Verify tables are dropped ---"
TABLE_COUNT=$(psql "$DB_URL" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('bots','bot_api_keys','validation_runs','validation_run_shares')")
if [[ "$TABLE_COUNT" == "0" ]]; then
  echo "  PASS: All 4 tables dropped successfully"
else
  echo "  FAIL: Expected 0 tables, found $TABLE_COUNT"
  exit 1
fi

KB_RLS=$(psql "$DB_URL" -tAc "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'kb_%' AND rowsecurity=true")
if [[ "$KB_RLS" == "0" ]]; then
  echo "  PASS: KB table RLS reverted to pre-003 state"
else
  echo "  FAIL: Expected 0 KB tables with RLS, found $KB_RLS"
  exit 1
fi

echo ""
echo "--- Step 5: Re-apply migration (idempotency test) ---"
psql "$DB_URL" -f "$MIGRATION_DIR/003_bot_registration_sharing.sql" 2>&1
echo "Re-apply complete."

echo ""
echo "--- Step 6: Final verification ---"
"$SCRIPT_DIR/verify-migration-003.sh" "$DB_URL" || {
  echo "ERROR: Re-apply verification failed."
  exit 1
}

echo ""
echo "=========================================="
echo "REHEARSAL COMPLETE: forward → rollback → re-apply all passed"
echo "=========================================="
