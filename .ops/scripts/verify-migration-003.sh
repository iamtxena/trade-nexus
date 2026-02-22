#!/usr/bin/env bash
# verify-migration-003.sh — RLS + schema verification for migration 003
# Usage: ./verify-migration-003.sh <DATABASE_URL>
# Exit codes: 0 = all checks pass, 1 = failures detected
set -euo pipefail

DB_URL="${1:?Usage: verify-migration-003.sh <DATABASE_URL>}"
PASS=0
FAIL=0

check() {
  local desc="$1"
  local query="$2"
  local expected="$3"
  local result
  result=$(psql "$DB_URL" -tAc "$query" 2>/dev/null || echo "ERROR")
  if [[ "$result" == "$expected" ]]; then
    echo "  PASS: $desc (got: $result)"
    ((PASS++))
  else
    echo "  FAIL: $desc (expected: $expected, got: $result)"
    ((FAIL++))
  fi
}

echo "=== Migration 003 Verification ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

echo "--- 1. New Tables Exist ---"
check "bots table exists" \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='bots'" \
  "1"
check "bot_api_keys table exists" \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='bot_api_keys'" \
  "1"
check "validation_runs table exists" \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='validation_runs'" \
  "1"
check "validation_run_shares table exists" \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='validation_run_shares'" \
  "1"

echo ""
echo "--- 2. RLS Enabled on New Tables ---"
check "bots RLS enabled" \
  "SELECT rowsecurity FROM pg_tables WHERE schemaname='public' AND tablename='bots'" \
  "t"
check "bot_api_keys RLS enabled" \
  "SELECT rowsecurity FROM pg_tables WHERE schemaname='public' AND tablename='bot_api_keys'" \
  "t"
check "validation_runs RLS enabled" \
  "SELECT rowsecurity FROM pg_tables WHERE schemaname='public' AND tablename='validation_runs'" \
  "t"
check "validation_run_shares RLS enabled" \
  "SELECT rowsecurity FROM pg_tables WHERE schemaname='public' AND tablename='validation_run_shares'" \
  "t"

echo ""
echo "--- 3. RLS Fixed on KB Tables ---"
check "kb_patterns RLS enabled" \
  "SELECT rowsecurity FROM pg_tables WHERE schemaname='public' AND tablename='kb_patterns'" \
  "t"
check "kb_market_regimes RLS enabled" \
  "SELECT rowsecurity FROM pg_tables WHERE schemaname='public' AND tablename='kb_market_regimes'" \
  "t"
check "kb_lessons_learned RLS enabled" \
  "SELECT rowsecurity FROM pg_tables WHERE schemaname='public' AND tablename='kb_lessons_learned'" \
  "t"
check "kb_macro_events RLS enabled" \
  "SELECT rowsecurity FROM pg_tables WHERE schemaname='public' AND tablename='kb_macro_events'" \
  "t"
check "kb_correlations RLS enabled" \
  "SELECT rowsecurity FROM pg_tables WHERE schemaname='public' AND tablename='kb_correlations'" \
  "t"

echo ""
echo "--- 4. Policy Counts ---"
check "bots has 1 policy" \
  "SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='bots'" \
  "1"
check "bot_api_keys has 1 policy" \
  "SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='bot_api_keys'" \
  "1"
check "validation_runs has 2 policies" \
  "SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='validation_runs'" \
  "2"
check "validation_run_shares has 2 policies" \
  "SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='validation_run_shares'" \
  "2"
check "kb_patterns has 4 policies" \
  "SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='kb_patterns'" \
  "4"

echo ""
echo "--- 5. FK Relationships ---"
check "bot_api_keys FK to bots" \
  "SELECT count(*) FROM pg_constraint WHERE contype='f' AND conrelid='bot_api_keys'::regclass" \
  "1"
check "validation_runs FK to bots" \
  "SELECT count(*) FROM pg_constraint WHERE contype='f' AND conrelid='validation_runs'::regclass AND confrelid='bots'::regclass" \
  "1"
check "validation_runs FK to strategies" \
  "SELECT count(*) FROM pg_constraint WHERE contype='f' AND conrelid='validation_runs'::regclass AND confrelid='strategies'::regclass" \
  "1"
check "validation_run_shares FK to validation_runs" \
  "SELECT count(*) FROM pg_constraint WHERE contype='f' AND conrelid='validation_run_shares'::regclass" \
  "1"

echo ""
echo "--- 6. Check Constraints ---"
check "bots status constraint" \
  "SELECT count(*) FROM pg_constraint WHERE contype='c' AND conrelid='bots'::regclass AND conname LIKE '%status%'" \
  "1"
check "bots registration_path constraint" \
  "SELECT count(*) FROM pg_constraint WHERE contype='c' AND conrelid='bots'::regclass AND conname LIKE '%registration_path%'" \
  "1"
check "validation_runs status constraint" \
  "SELECT count(*) FROM pg_constraint WHERE contype='c' AND conrelid='validation_runs'::regclass AND conname LIKE '%status%'" \
  "1"
check "validation_run_shares access_level constraint" \
  "SELECT count(*) FROM pg_constraint WHERE contype='c' AND conrelid='validation_run_shares'::regclass AND conname LIKE '%access_level%'" \
  "1"

echo ""
echo "--- 7. Unique Constraints / Indexes ---"
check "bots unique user+name index" \
  "SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND tablename='bots' AND indexname='idx_bots_user_name'" \
  "1"
check "shares unique run+email index" \
  "SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND tablename='validation_run_shares' AND indexname='idx_shares_unique'" \
  "1"

echo ""
echo "==================================="
echo "Results: $PASS passed, $FAIL failed"
echo "==================================="

if [[ $FAIL -gt 0 ]]; then
  echo "VERIFICATION FAILED"
  exit 1
else
  echo "ALL CHECKS PASSED"
  exit 0
fi
