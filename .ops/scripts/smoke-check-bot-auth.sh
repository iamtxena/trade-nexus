#!/usr/bin/env bash
# smoke-check-bot-auth.sh — Smoke tests for bot registration + sharing auth flows
# Usage: ./smoke-check-bot-auth.sh <BACKEND_URL>
# Tests API-level auth enforcement (does NOT create real bots)
set -euo pipefail

BASE_URL="${1:?Usage: smoke-check-bot-auth.sh <BACKEND_URL>}"
PASS=0
FAIL=0

smoke() {
  local desc="$1"
  local method="$2"
  local path="$3"
  local expected_status="$4"  # supports pipe-separated alternatives e.g. "401|403"
  local body="${5:-}"

  local args=(-s -o /dev/null -w "%{http_code}" -X "$method")
  args+=("${BASE_URL}${path}")
  args+=(-H "Content-Type: application/json")

  if [[ -n "$body" ]]; then
    args+=(-d "$body")
  fi

  local status
  status=$(curl "${args[@]}" 2>/dev/null || echo "000")

  # Support pipe-separated expected statuses (e.g. "401|403")
  local match=false
  IFS='|' read -ra expected_codes <<< "$expected_status"
  for code in "${expected_codes[@]}"; do
    if [[ "$status" == "$code" ]]; then
      match=true
      break
    fi
  done

  if [[ "$match" == "true" ]]; then
    echo "  PASS: $desc (HTTP $status)"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc (expected HTTP $expected_status, got $status)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== Bot Auth Smoke Checks ==="
echo "Target: $BASE_URL"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

echo "--- 1. Health Check ---"
smoke "Health endpoint accessible" GET "/health" "200"

echo ""
echo "--- 2. Unauthenticated Access (should be rejected) ---"
smoke "Bot list without auth → 401" GET "/v1/bots" "401"
smoke "Bot create without auth → 401" POST "/v1/bots" "401" '{"name":"test"}'
smoke "Validation runs without auth → 401" GET "/v1/validation-runs" "401"
smoke "Share without auth → 401" POST "/v1/validation-runs/shares" "401" '{"run_id":"fake","email":"a@b.com"}'

echo ""
echo "--- 3. Invalid Partner Key (should be rejected) ---"
smoke "Bot register with bad partner key → 401 or 403" \
  POST "/v1/bots/register" "401|403" \
  '{"name":"bad-bot","partner_key":"invalid-key-12345"}'

echo ""
echo "--- 4. Existing Endpoints Still Work ---"
smoke "Strategies list without auth → 401 (auth enforced)" GET "/v1/strategies" "401"
smoke "Root endpoint → 200" GET "/" "200"

echo ""
echo "==================================="
echo "Results: $PASS passed, $FAIL failed"
echo "==================================="

if [[ $FAIL -gt 0 ]]; then
  echo "SMOKE CHECK ISSUES DETECTED"
  echo "Note: Some failures are expected if bot registration endpoints are not yet deployed."
  echo "Re-run after backend deployment to confirm."
  exit 1
else
  echo "ALL SMOKE CHECKS PASSED"
  exit 0
fi
