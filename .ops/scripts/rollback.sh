#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# rollback.sh — Revert traffic to a previous Azure Container App revision
#
# Usage: ./rollback.sh [revision-name] [--yes]
# Exit:  0 = rollback succeeded + smoke passed
#        1 = rollback or smoke failed
#        2 = cannot rollback (only one revision)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER_APP="trade-nexus-backend"
RESOURCE_GROUP="trade-nexus"
FQDN="trade-nexus-backend.whitecliff-198cd26a.westeurope.azurecontainerapps.io"
AUTO_CONFIRM=false
TARGET_REVISION=""

# --- Cleanup / trap --------------------------------------------------------
cleanup() {
  : # Nothing to clean up currently; placeholder for future use
}
trap cleanup EXIT

# --- Parse arguments --------------------------------------------------------
if [[ $# -gt 0 && "$1" != "--"* ]]; then
  TARGET_REVISION="$1"
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes) AUTO_CONFIRM=true; shift ;;
    *)     shift ;;
  esac
done

# --- Helpers ----------------------------------------------------------------
confirm_action() {
  local message="$1"
  if [[ "$AUTO_CONFIRM" == "true" ]]; then
    return 0
  fi
  echo ""
  echo "  WARNING: $message"
  read -rp "  Continue? [y/N] " response
  case "$response" in
    [yY]|[yY][eE][sS]) return 0 ;;
    *) echo "Aborted by user."; exit 1 ;;
  esac
}

iso_timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

epoch_seconds() {
  date +%s
}

# =============================================================================
# Main
# =============================================================================
echo "=== ROLLBACK ==="
echo "Container App: ${CONTAINER_APP}"
echo "Resource Group: ${RESOURCE_GROUP}"
echo ""

# --- 1. List revisions sorted by creation time (newest first) ---------------
echo "Fetching revisions..."
AZ_STDERR=$(mktemp)
REVISIONS_JSON=$(az containerapp revision list \
  --name "$CONTAINER_APP" \
  --resource-group "$RESOURCE_GROUP" \
  -o json 2>"$AZ_STDERR") || {
  echo "ERROR: Failed to list revisions:"
  cat "$AZ_STDERR" >&2
  rm -f "$AZ_STDERR"
  exit 1
}
if [[ -s "$AZ_STDERR" ]]; then
  echo "  az warnings: $(cat "$AZ_STDERR")" >&2
fi
rm -f "$AZ_STDERR"

REVISION_COUNT=$(echo "$REVISIONS_JSON" | jq 'length')

if (( REVISION_COUNT < 2 )); then
  echo "ROLLBACK_RESULT status=SKIP reason=\"Cannot rollback: only one revision exists\""
  exit 2
fi

# Sort by createdTime descending
SORTED_REVISIONS=$(echo "$REVISIONS_JSON" | jq -r '[.[] | {name: .name, active: .properties.active, created: .properties.createdTime}] | sort_by(.created) | reverse')

echo "Found ${REVISION_COUNT} revisions:"
echo "$SORTED_REVISIONS" | jq -r '.[] | "  \(.name)  active=\(.active)  created=\(.created)"'
echo ""

# --- 2. Identify current and target revisions ------------------------------
# Current = the one receiving traffic (first active, newest)
CURRENT_REVISION=$(echo "$SORTED_REVISIONS" | jq -r '[.[] | select(.active == true)] | .[0].name')

if [[ -z "$TARGET_REVISION" || "$TARGET_REVISION" == "null" ]]; then
  # Target = the next revision after current (by creation time)
  TARGET_REVISION=$(echo "$SORTED_REVISIONS" | jq -r --arg current "$CURRENT_REVISION" '[.[] | select(.name != $current)] | .[0].name')
fi

if [[ -z "$TARGET_REVISION" || "$TARGET_REVISION" == "null" ]]; then
  echo "ERROR: Could not determine target revision for rollback."
  exit 1
fi

echo "Current revision: ${CURRENT_REVISION}"
echo "Target revision:  ${TARGET_REVISION}"

confirm_action "This will shift 100% traffic from '${CURRENT_REVISION}' to '${TARGET_REVISION}'."

# --- 3. Start rollback -----------------------------------------------------
START_TS=$(iso_timestamp)
START_EPOCH=$(epoch_seconds)

echo ""
echo "ROLLBACK_START revision=${TARGET_REVISION} timestamp=${START_TS}"

# --- 4. Activate target revision if deactivated ----------------------------
TARGET_ACTIVE=$(echo "$SORTED_REVISIONS" | jq -r --arg target "$TARGET_REVISION" '.[] | select(.name == $target) | .active')

if [[ "$TARGET_ACTIVE" != "true" ]]; then
  echo "Activating deactivated revision: ${TARGET_REVISION}..."
  az containerapp revision activate \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --revision "$TARGET_REVISION" \
    -o none 2>&1
  echo "  Revision activated."
fi

# --- 5. Shift 100% traffic to target revision ------------------------------
# Detect revision mode to determine if explicit traffic set is needed
REVISION_MODE=$(az containerapp show \
  --name "$CONTAINER_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.activeRevisionsMode" \
  -o tsv 2>/dev/null || echo "single")

echo "Revision mode: ${REVISION_MODE}"
echo "Shifting traffic to ${TARGET_REVISION}..."

if [[ "$REVISION_MODE" == "multiple" || "$REVISION_MODE" == "Multiple" ]]; then
  # Multi-revision mode: explicit traffic shift is required
  AZ_TRAFFIC_STDERR=$(mktemp)
  set +e
  az containerapp ingress traffic set \
    --name "$CONTAINER_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --revision-weight "${TARGET_REVISION}=100" \
    -o none 2>"$AZ_TRAFFIC_STDERR"
  TRAFFIC_EXIT=$?
  set -e

  if [[ $TRAFFIC_EXIT -eq 0 ]]; then
    echo "ROLLBACK_TRAFFIC_SHIFT status=OK"
  else
    echo "ROLLBACK_TRAFFIC_SHIFT status=FAIL"
    echo "  ERROR: Traffic shift failed (exit=${TRAFFIC_EXIT}):"
    cat "$AZ_TRAFFIC_STDERR" >&2
    rm -f "$AZ_TRAFFIC_STDERR"
    END_EPOCH=$(epoch_seconds)
    DURATION=$(( END_EPOCH - START_EPOCH ))
    echo "ROLLBACK_RESULT status=FAIL duration_seconds=${DURATION} from=${CURRENT_REVISION} to=${TARGET_REVISION} reason=traffic_shift_failed"
    exit 1
  fi
  rm -f "$AZ_TRAFFIC_STDERR"
else
  # Single-revision mode: traffic auto-routes to the only active revision.
  # Deactivate current and activate target to ensure correct routing.
  if [[ "$CURRENT_REVISION" != "$TARGET_REVISION" ]]; then
    echo "  Single-revision mode: deactivating ${CURRENT_REVISION}, traffic will route to ${TARGET_REVISION}."
    az containerapp revision deactivate \
      --name "$CONTAINER_APP" \
      --resource-group "$RESOURCE_GROUP" \
      --revision "$CURRENT_REVISION" \
      -o none 2>/dev/null || true
  fi
  echo "ROLLBACK_TRAFFIC_SHIFT status=OK mode=single-revision"
fi

# --- 6. Smoke check --------------------------------------------------------
echo ""
echo "Running smoke check..."
set +e
"${SCRIPT_DIR}/smoke-check.sh" --url "https://${FQDN}"
SMOKE_EXIT=$?
set -e

END_EPOCH=$(epoch_seconds)
DURATION=$(( END_EPOCH - START_EPOCH ))

echo ""

if [[ $SMOKE_EXIT -eq 0 ]]; then
  echo "ROLLBACK_SMOKE status=PASS"
  echo "ROLLBACK_RESULT status=PASS duration_seconds=${DURATION} from=${CURRENT_REVISION} to=${TARGET_REVISION}"
  exit 0
else
  echo "ROLLBACK_SMOKE status=FAIL"
  echo ""
  echo "  WARNING: Smoke check failed after traffic shift!"
  echo "  Traffic is now pointing to: ${TARGET_REVISION}"
  echo "  Manual intervention may be required."
  echo ""
  echo "ROLLBACK_RESULT status=FAIL duration_seconds=${DURATION} from=${CURRENT_REVISION} to=${TARGET_REVISION}"
  exit 1
fi
