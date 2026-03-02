#!/usr/bin/env bash
# verify-migration-009.sh — RLS + schema verification for migration 009
# Usage: ./verify-migration-009.sh <DATABASE_URL>
# Exit codes: 0 = all checks pass, 1 = failures detected
set -euo pipefail

DB_URL="${1:?Usage: verify-migration-009.sh <DATABASE_URL>}"
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
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc (expected: $expected, got: $result)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Migration 009 Verification ==="
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

echo "--- 1. Tables Exist ---"
check "cli_device_authorizations table exists" \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='cli_device_authorizations'" \
  "1"
check "cli_sessions table exists" \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='cli_sessions'" \
  "1"

echo ""
echo "--- 2. RLS Enabled ---"
check "cli_device_authorizations RLS enabled" \
  "SELECT rowsecurity FROM pg_tables WHERE schemaname='public' AND tablename='cli_device_authorizations'" \
  "t"
check "cli_sessions RLS enabled" \
  "SELECT rowsecurity FROM pg_tables WHERE schemaname='public' AND tablename='cli_sessions'" \
  "t"

echo ""
echo "--- 3. Policy Counts ---"
check "cli_device_authorizations has 1 policy" \
  "SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='cli_device_authorizations'" \
  "1"
check "cli_sessions has 2 policies" \
  "SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename='cli_sessions'" \
  "2"

echo ""
echo "--- 4. Check Constraints ---"
check "cli_device_authorizations status constraint" \
  "SELECT count(*) FROM pg_constraint WHERE contype='c' AND conrelid='cli_device_authorizations'::regclass AND conname LIKE '%status%'" \
  "1"

echo ""
echo "--- 5. Unique Indexes ---"
check "device_code_hash unique index" \
  "SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND tablename='cli_device_authorizations' AND indexname='idx_cli_device_auth_device_code_hash'" \
  "1"
check "user_code_hash unique index" \
  "SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND tablename='cli_device_authorizations' AND indexname='idx_cli_device_auth_user_code_hash'" \
  "1"
check "status index" \
  "SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND tablename='cli_device_authorizations' AND indexname='idx_cli_device_auth_status'" \
  "1"
check "device_auth expires_at index" \
  "SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND tablename='cli_device_authorizations' AND indexname='idx_cli_device_auth_expires_at'" \
  "1"

echo ""
echo "--- 6. Session Indexes ---"
check "tenant_user index" \
  "SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND tablename='cli_sessions' AND indexname='idx_cli_sessions_tenant_user'" \
  "1"
check "token_hash index" \
  "SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND tablename='cli_sessions' AND indexname='idx_cli_sessions_token_hash'" \
  "1"
check "sessions expires_at index" \
  "SELECT count(*) FROM pg_indexes WHERE schemaname='public' AND tablename='cli_sessions' AND indexname='idx_cli_sessions_expires_at'" \
  "1"

echo ""
echo "--- 7. Unique Constraint Enforcement ---"
check "device_code_hash is unique" \
  "SELECT indisunique FROM pg_index WHERE indexrelid = 'idx_cli_device_auth_device_code_hash'::regclass" \
  "t"
check "user_code_hash is unique" \
  "SELECT indisunique FROM pg_index WHERE indexrelid = 'idx_cli_device_auth_user_code_hash'::regclass" \
  "t"

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
