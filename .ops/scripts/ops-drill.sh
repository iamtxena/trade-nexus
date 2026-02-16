#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# ops-drill.sh — Run ops drill scenarios individually or all at once
#
# Usage: ./ops-drill.sh {1|2|3|4|5|all} [--yes]
# Exit:  0 = all run scenarios passed, 1 = one or more failed
#
# Scenarios:
#   1 — Health check validation (read-only)
#   2 — Scale-from-zero latency measurement (read-only, minimal risk)
#   3 — Rollback drill (write, low risk)
#   4 — Emergency shutdown (write, medium risk, ~30-60s downtime)
#   5 — Secret rotation simulation (read-only)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER_APP="trade-nexus-backend"
RESOURCE_GROUP="trade-nexus"
FQDN="trade-nexus-backend.whitecliff-198cd26a.westeurope.azurecontainerapps.io"
AUTO_CONFIRM=false
RESULTS=()
HAS_FAILURE=false

# --- Cleanup / trap --------------------------------------------------------
cleanup() {
  : # Placeholder; individual scenarios handle their own cleanup
}
trap cleanup EXIT

# --- Parse arguments --------------------------------------------------------
SCENARIO="${1:-}"
shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes) AUTO_CONFIRM=true; shift ;;
    *)     shift ;;
  esac
done

# --- Helpers ----------------------------------------------------------------
iso_timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

epoch_seconds() {
  date +%s
}

confirm_or_skip() {
  local message="$1"
  local scenario_num="$2"
  local scenario_name="$3"

  if [[ "$AUTO_CONFIRM" == "true" ]]; then
    return 0
  fi

  echo ""
  echo "  WARNING: ${message}"
  read -rp "  Proceed with scenario ${scenario_num}? [y/N] " response
  case "$response" in
    [yY]|[yY][eE][sS]) return 0 ;;
    *)
      echo "  Skipped by user."
      RESULTS+=("DRILL_RESULT scenario=${scenario_num} name=\"${scenario_name}\" status=SKIP duration_seconds=0")
      return 1
      ;;
  esac
}

record_result() {
  local scenario_num="$1"
  local name="$2"
  local status="$3"
  local duration="$4"
  local entry="DRILL_RESULT scenario=${scenario_num} name=\"${name}\" status=${status} duration_seconds=${duration}"
  RESULTS+=("$entry")
  echo "$entry"
  if [[ "$status" == "FAIL" ]]; then
    HAS_FAILURE=true
  fi
}

# =============================================================================
# Scenario 1: Health check validation (read-only, no risk)
# =============================================================================
run_scenario_1() {
  local name="Health check validation"
  echo ""
  echo "=== Scenario 1: ${name} ==="
  local start
  start=$(epoch_seconds)

  set +e
  "${SCRIPT_DIR}/smoke-check.sh" --url "https://${FQDN}"
  local smoke_exit=$?
  set -e

  local end
  end=$(epoch_seconds)
  local duration=$(( end - start ))

  if [[ $smoke_exit -eq 0 ]]; then
    record_result 1 "$name" "PASS" "$duration"
  else
    record_result 1 "$name" "FAIL" "$duration"
  fi
}

# =============================================================================
# Scenario 2: Scale-from-zero latency measurement (read-only, minimal risk)
# =============================================================================
run_scenario_2() {
  local name="Scale-from-zero latency"
  echo ""
  echo "=== Scenario 2: ${name} ==="

  if ! confirm_or_skip "This will deactivate the revision temporarily to force scale-to-zero, then reactivate and measure cold-start latency." 2 "$name"; then
    return 0
  fi

  local start
  start=$(epoch_seconds)

  # Get current active revision
  local revisions_json
  revisions_json=$(az containerapp revision list \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    -o json 2>&1)

  local active_revision
  active_revision=$(echo "$revisions_json" | jq -r '[.[] | select(.properties.active == true)] | sort_by(.properties.createdTime) | reverse | .[0].name')

  echo "Active revision: ${active_revision}"

  # Deactivate revision to force scale-to-zero
  echo "Deactivating revision to force scale-to-zero..."
  az containerapp revision deactivate \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --revision "$active_revision" \
    -o none 2>&1

  echo "Waiting 10s for scale-down..."
  sleep 10

  # Reactivate and measure cold-start
  echo "Reactivating revision..."
  az containerapp revision activate \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --revision "$active_revision" \
    -o none 2>&1

  echo "Running smoke check (will trigger cold start)..."

  set +e
  SMOKE_OUTPUT=$("${SCRIPT_DIR}/smoke-check.sh" --url "https://${FQDN}" 2>&1)
  local smoke_exit=$?
  set -e

  echo "$SMOKE_OUTPUT"

  local end
  end=$(epoch_seconds)
  local duration=$(( end - start ))

  # Parse cold-start seconds from smoke output
  local cold_start_seconds
  cold_start_seconds=$(echo "$SMOKE_OUTPUT" | grep "SMOKE_RESULT" | sed 's/.*cold_start_seconds=//' | awk '{print $1}')
  cold_start_seconds="${cold_start_seconds:-0}"

  echo ""
  echo "Cold-start latency: ${cold_start_seconds}s (SLO: p95 < 45s)"

  # Compare to SLO: cold start < 45s
  local within_slo
  within_slo=$(awk "BEGIN {print (${cold_start_seconds} < 45) ? \"true\" : \"false\"}")

  if [[ $smoke_exit -eq 0 && "$within_slo" == "true" ]]; then
    record_result 2 "$name" "PASS" "$duration"
  elif [[ $smoke_exit -eq 0 && "$within_slo" == "false" ]]; then
    echo "  Cold-start exceeded SLO (${cold_start_seconds}s > 45s)"
    record_result 2 "$name" "FAIL" "$duration"
  else
    record_result 2 "$name" "FAIL" "$duration"
  fi
}

# =============================================================================
# Scenario 3: Rollback drill (write, low risk)
# =============================================================================
run_scenario_3() {
  local name="Rollback drill"
  echo ""
  echo "=== Scenario 3: ${name} ==="

  local start
  start=$(epoch_seconds)

  # Check revision count
  local revisions_json
  revisions_json=$(az containerapp revision list \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    -o json 2>&1)

  local rev_count
  rev_count=$(echo "$revisions_json" | jq 'length')

  if (( rev_count < 2 )); then
    echo "  Only ${rev_count} revision(s) found. Cannot perform rollback drill."
    local end
    end=$(epoch_seconds)
    record_result 3 "$name" "SKIP" "$(( end - start ))"
    return 0
  fi

  if ! confirm_or_skip "This will perform a rollback (traffic shift) and then restore. Low risk but involves write operations." 3 "$name"; then
    return 0
  fi

  # Identify current revision (for restore later)
  local sorted_revisions
  sorted_revisions=$(echo "$revisions_json" | jq -r '[.[] | {name: .name, active: .properties.active, created: .properties.createdTime}] | sort_by(.created) | reverse')

  local current_revision
  current_revision=$(echo "$sorted_revisions" | jq -r '[.[] | select(.active == true)] | .[0].name')

  echo "Current revision: ${current_revision}"
  echo ""

  # Step 1: Rollback to previous
  echo "--- Step 1: Rollback to previous revision ---"
  local yes_flag=""
  if [[ "$AUTO_CONFIRM" == "true" ]]; then
    yes_flag="--yes"
  fi

  set +e
  "${SCRIPT_DIR}/rollback.sh" $yes_flag
  local rollback1_exit=$?
  set -e

  if [[ $rollback1_exit -ne 0 ]]; then
    echo "  First rollback failed (exit=${rollback1_exit})"
    local end
    end=$(epoch_seconds)
    record_result 3 "$name" "FAIL" "$(( end - start ))"
    return 0
  fi

  echo ""
  echo "--- Step 2: Restore to original revision ---"

  set +e
  "${SCRIPT_DIR}/rollback.sh" "$current_revision" $yes_flag
  local rollback2_exit=$?
  set -e

  local end
  end=$(epoch_seconds)
  local duration=$(( end - start ))

  if [[ $rollback2_exit -eq 0 ]]; then
    echo "  Original revision restored successfully."
    record_result 3 "$name" "PASS" "$duration"
  else
    echo "  WARNING: Failed to restore original revision '${current_revision}'"
    echo "  Manual intervention may be required."
    record_result 3 "$name" "FAIL" "$duration"
  fi
}

# =============================================================================
# Scenario 4: Emergency shutdown (write, medium risk, ~30-60s downtime)
# =============================================================================
run_scenario_4() {
  local name="Emergency shutdown"
  echo ""
  echo "=== Scenario 4: ${name} ==="

  if ! confirm_or_skip "THIS WILL CAUSE ~30-60s OF DOWNTIME. The app will be scaled to 0 replicas and then restored." 4 "$name"; then
    return 0
  fi

  local start
  start=$(epoch_seconds)

  # Get current active revision
  echo "Reading current revision..."
  local revisions_json
  revisions_json=$(az containerapp revision list \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    -o json 2>&1)

  local active_revision
  active_revision=$(echo "$revisions_json" | jq -r '[.[] | select(.properties.active == true)] | sort_by(.properties.createdTime) | reverse | .[0].name')

  echo "Active revision: ${active_revision}"

  # Deactivate revision (emergency shutdown)
  echo "Deactivating revision (emergency shutdown)..."
  local shutdown_start
  shutdown_start=$(epoch_seconds)

  az containerapp revision deactivate \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --revision "$active_revision" \
    -o none 2>&1

  echo "Waiting 15s for shutdown..."
  sleep 15

  # Verify the app is down (expect connection failure or 503)
  echo "Verifying app is down..."
  set +e
  local verify_status
  verify_status=$(curl -s -o /dev/null -w "%{http_code}" \
    --connect-timeout 5 \
    --max-time 10 \
    "https://${FQDN}/health" 2>&1)
  local verify_exit=$?
  set -e

  if [[ $verify_exit -ne 0 || "$verify_status" == "503" || "$verify_status" == "000" || "$verify_status" == "502" ]]; then
    echo "  App confirmed down (status=${verify_status}, curl_exit=${verify_exit})"
  else
    echo "  WARNING: App may still be responding (status=${verify_status})"
  fi

  # Restore: reactivate revision
  echo "Reactivating revision ${active_revision}..."
  az containerapp revision activate \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --revision "$active_revision" \
    -o none 2>&1

  echo "Revision reactivated. Running smoke check for recovery..."

  # Smoke check (retries for up to 60s)
  set +e
  "${SCRIPT_DIR}/smoke-check.sh" --url "https://${FQDN}"
  local smoke_exit=$?
  set -e

  local recovery_end
  recovery_end=$(epoch_seconds)
  local downtime=$(( recovery_end - shutdown_start ))

  local end
  end=$(epoch_seconds)
  local duration=$(( end - start ))

  echo ""
  echo "Total downtime: ${downtime}s"

  if [[ $smoke_exit -eq 0 && $downtime -le 120 ]]; then
    echo "  Recovery succeeded within 120s window."
    record_result 4 "$name" "PASS" "$duration"
  elif [[ $smoke_exit -eq 0 ]]; then
    echo "  Recovery succeeded but took ${downtime}s (> 120s limit)."
    record_result 4 "$name" "FAIL" "$duration"
  else
    echo "  Recovery FAILED. App may still be down!"
    record_result 4 "$name" "FAIL" "$duration"
  fi
}

# =============================================================================
# Scenario 5: Secret rotation simulation (read-only, no risk)
# =============================================================================
run_scenario_5() {
  local name="Secret rotation simulation"
  echo ""
  echo "=== Scenario 5: ${name} ==="

  local start
  start=$(epoch_seconds)

  local expected_secrets=("xai-api-key" "supabase-key" "langsmith-api-key" "lona-agent-token")

  echo "Checking for expected secrets on ${CONTAINER_APP}..."
  echo "Expected: ${expected_secrets[*]}"
  echo ""

  # Fetch container app config
  local app_json
  app_json=$(az containerapp show \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    -o json 2>&1)

  # Extract secret names (values are never exposed)
  local actual_secrets
  actual_secrets=$(echo "$app_json" | jq -r '[.properties.configuration.secrets[]?.name] // []')

  local all_present=true
  for secret in "${expected_secrets[@]}"; do
    local found
    found=$(echo "$actual_secrets" | jq -r --arg s "$secret" 'map(select(. == $s)) | length')
    if [[ "$found" -gt 0 ]]; then
      echo "  [OK] ${secret}"
    else
      echo "  [MISSING] ${secret}"
      all_present=false
    fi
  done

  local end
  end=$(epoch_seconds)
  local duration=$(( end - start ))

  echo ""
  if [[ "$all_present" == "true" ]]; then
    echo "  All ${#expected_secrets[@]} secrets present (values NOT inspected)."
    record_result 5 "$name" "PASS" "$duration"
  else
    echo "  One or more secrets MISSING."
    record_result 5 "$name" "FAIL" "$duration"
  fi
}

# =============================================================================
# Main — dispatch
# =============================================================================
if [[ -z "$SCENARIO" ]]; then
  echo "Usage: $0 {1|2|3|4|5|all} [--yes]"
  echo ""
  echo "Scenarios:"
  echo "  1  Health check validation (read-only)"
  echo "  2  Scale-from-zero latency measurement (minimal risk)"
  echo "  3  Rollback drill (write, low risk)"
  echo "  4  Emergency shutdown (write, ~30-60s downtime)"
  echo "  5  Secret rotation simulation (read-only)"
  echo "  all  Run all scenarios"
  exit 1
fi

echo "=== OPS DRILL ==="
echo "Container App: ${CONTAINER_APP}"
echo "Resource Group: ${RESOURCE_GROUP}"
echo "Timestamp: $(iso_timestamp)"

case "${SCENARIO}" in
  1) run_scenario_1 ;;
  2) run_scenario_2 ;;
  3) run_scenario_3 ;;
  4) run_scenario_4 ;;
  5) run_scenario_5 ;;
  all)
    for i in 1 2 3 4 5; do
      "run_scenario_${i}"
    done
    ;;
  *)
    echo "Unknown scenario: ${SCENARIO}"
    echo "Usage: $0 {1|2|3|4|5|all} [--yes]"
    exit 1
    ;;
esac

# --- Print summary ----------------------------------------------------------
echo ""
echo "=== DRILL SUMMARY ==="
for r in "${RESULTS[@]}"; do
  echo "$r"
done

# Exit with failure if any scenario failed
if [[ "$HAS_FAILURE" == "true" ]]; then
  exit 1
fi

exit 0
