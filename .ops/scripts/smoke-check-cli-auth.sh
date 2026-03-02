#!/usr/bin/env bash
# smoke-check-cli-auth.sh — Smoke tests for CLI auth device-flow endpoints
# Usage: ./smoke-check-cli-auth.sh <BACKEND_URL>
# Tests API-level auth enforcement (does NOT perform real JWT approval)
set -euo pipefail

BASE_URL="${1:?Usage: smoke-check-cli-auth.sh <BACKEND_URL>}"
BASE_URL="${BASE_URL%/}"
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

echo "=== CLI Auth Smoke Checks ==="
echo "Target: $BASE_URL"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

echo "--- 1. Device Flow Start ---"
# POST /v2/validation-cli-auth/device/start should accept unauthenticated requests
# and return 201 with deviceCode, userCode, verificationUri, expiresAt
smoke "Device start returns 201" \
  POST "/v2/validation-cli-auth/device/start" "201" \
  '{"scopes":["validation:read"]}'

echo ""
echo "--- 2. Token Poll Before Approval ---"
# Polling before approval should return 409 with CLI_DEVICE_AUTHORIZATION_PENDING
smoke "Token poll before approval returns 409" \
  POST "/v2/validation-cli-auth/device/token" "409" \
  '{"device_code":"fake-device-code-000000"}'

echo ""
echo "--- 3. Approval Without Auth (negative test) ---"
# Approval requires a valid Clerk JWT; without auth should return 401 or 403
smoke "Approve without auth rejected" \
  POST "/v2/validation-cli-auth/device/approve" "401|403" \
  '{"user_code":"FAKE-CODE"}'

echo ""
echo "--- 4. Whoami Without Token ---"
# /whoami requires a valid CLI session token
smoke "Whoami without token returns 401" \
  GET "/v2/validation-cli-auth/whoami" "401"

echo ""
echo "--- 5. Revoke Without Auth ---"
# Revoking a session requires authentication
smoke "Revoke without auth returns 401" \
  POST "/v2/validation-cli-auth/sessions/fake-session/revoke" "401|403"

echo ""
echo "--- 6. Introspect Without Auth ---"
# Token introspection requires authentication
smoke "Introspect without auth returns 401" \
  POST "/v2/validation-cli-auth/introspect" "401|403" \
  '{"token":"fake-token"}'

echo ""
echo "==================================="
echo "Results: $PASS passed, $FAIL failed"
echo "==================================="

if [[ $FAIL -gt 0 ]]; then
  echo "SMOKE CHECK ISSUES DETECTED"
  echo "Note: Step 1-2 may fail if CLI auth endpoints are not yet deployed."
  echo "Steps 3-6 test auth enforcement (should pass if auth middleware is active)."
  echo "Full E2E with real JWT approval is a manual UAT step (see runbook)."
  exit 1
else
  echo "ALL SMOKE CHECKS PASSED"
  exit 0
fi
