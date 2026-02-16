#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# smoke-check.sh — Post-deploy health validation with cold-start retry
#
# Usage: ./smoke-check.sh [--url <URL>]
# Exit:  0 = all endpoints healthy, 1 = one or more endpoints failed
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_URL="https://trade-nexus-backend.whitecliff-198cd26a.westeurope.azurecontainerapps.io"
BASE_URL="${DEFAULT_URL}"

# --- Cleanup / trap --------------------------------------------------------
TMPFILES=()
cleanup() {
  for f in "${TMPFILES[@]}"; do
    rm -f "$f" 2>/dev/null || true
  done
}
trap cleanup EXIT

# --- Parse arguments --------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --url)
      BASE_URL="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# Strip trailing slash
BASE_URL="${BASE_URL%/}"

# --- Constants --------------------------------------------------------------
ENDPOINTS=("/health" "/v1/health")
MAX_RETRIES=12
RETRY_INTERVAL=5
COLD_START_THRESHOLD=10  # seconds — latency above this = cold start
CONNECT_TIMEOUT=10
MAX_TIME=30

# --- State ------------------------------------------------------------------
OVERALL_PASS=true
COLD_START_DETECTED=false
COLD_START_SECONDS=0
FIRST_REQUEST_DONE=false

# =============================================================================
# check_endpoint — curl an endpoint with retries for cold start
#   $1 = path (e.g. /health)
# =============================================================================
check_endpoint() {
  local path="$1"
  local url="${BASE_URL}${path}"
  local attempt=0
  local status_code=""
  local latency_raw=""
  local latency_ms=""
  local is_cold_start="false"
  local success=false

  while (( attempt < MAX_RETRIES )); do
    attempt=$(( attempt + 1 ))

    # Create temp file for response body
    local tmpfile
    tmpfile=$(mktemp)
    TMPFILES+=("$tmpfile")

    # curl: -s silent, -o body, -w timing, --connect-timeout, --max-time
    set +e
    local curl_output
    curl_output=$(curl -s -o "$tmpfile" \
      -w "%{http_code} %{time_total}" \
      --connect-timeout "$CONNECT_TIMEOUT" \
      --max-time "$MAX_TIME" \
      "$url" 2>&1)
    local curl_exit=$?
    set -e

    if [[ $curl_exit -ne 0 ]]; then
      echo "SMOKE_CHECK endpoint=${path} attempt=${attempt}/${MAX_RETRIES} status=CONNECT_FAIL curl_exit=${curl_exit}"
      if (( attempt < MAX_RETRIES )); then
        echo "  Retrying in ${RETRY_INTERVAL}s (cold-start window)..."
        sleep "$RETRY_INTERVAL"
        continue
      else
        echo "SMOKE_CHECK endpoint=${path} status=FAIL reason=max_retries_exhausted"
        OVERALL_PASS=false
        return
      fi
    fi

    # Parse curl output: "<status_code> <time_total>"
    status_code=$(echo "$curl_output" | awk '{print $1}')
    latency_raw=$(echo "$curl_output" | awk '{print $2}')

    # Convert seconds to milliseconds (integer)
    latency_ms=$(awk "BEGIN {printf \"%.0f\", ${latency_raw} * 1000}")

    if [[ "$status_code" == "200" ]]; then
      success=true

      # Detect cold start on first successful request
      if [[ "$FIRST_REQUEST_DONE" == "false" ]]; then
        FIRST_REQUEST_DONE=true
        local latency_int=${latency_raw%.*}
        # Compare with threshold (handle decimals via awk)
        is_cold_start=$(awk "BEGIN {print (${latency_raw} > ${COLD_START_THRESHOLD}) ? \"true\" : \"false\"}")
        if [[ "$is_cold_start" == "true" ]]; then
          COLD_START_DETECTED=true
          COLD_START_SECONDS=$(awk "BEGIN {printf \"%.1f\", ${latency_raw}}")
        fi
      fi

      echo "SMOKE_CHECK endpoint=${path} status=${status_code} latency_ms=${latency_ms} cold_start=${is_cold_start}"

      # If this was a cold start, do a warm follow-up for comparison
      if [[ "$is_cold_start" == "true" ]]; then
        sleep 1
        local warm_tmp
        warm_tmp=$(mktemp)
        TMPFILES+=("$warm_tmp")
        set +e
        local warm_output
        warm_output=$(curl -s -o "$warm_tmp" \
          -w "%{http_code} %{time_total}" \
          --connect-timeout "$CONNECT_TIMEOUT" \
          --max-time "$MAX_TIME" \
          "$url" 2>&1)
        set -e
        local warm_status warm_latency warm_ms
        warm_status=$(echo "$warm_output" | awk '{print $1}')
        warm_latency=$(echo "$warm_output" | awk '{print $2}')
        warm_ms=$(awk "BEGIN {printf \"%.0f\", ${warm_latency} * 1000}")
        echo "SMOKE_CHECK endpoint=${path} status=${warm_status} latency_ms=${warm_ms} cold_start=false (warm follow-up)"
      fi

      break
    else
      echo "SMOKE_CHECK endpoint=${path} attempt=${attempt}/${MAX_RETRIES} status=${status_code} latency_ms=${latency_ms}"
      if (( attempt < MAX_RETRIES )); then
        echo "  Retrying in ${RETRY_INTERVAL}s..."
        sleep "$RETRY_INTERVAL"
      else
        echo "SMOKE_CHECK endpoint=${path} status=FAIL final_status=${status_code}"
        OVERALL_PASS=false
        return
      fi
    fi
  done

  if [[ "$success" == "false" ]]; then
    OVERALL_PASS=false
  fi
}

# =============================================================================
# Main
# =============================================================================
echo "=== SMOKE CHECK ==="
echo "Target: ${BASE_URL}"
echo "Endpoints: ${ENDPOINTS[*]}"
echo "Max retries: ${MAX_RETRIES} x ${RETRY_INTERVAL}s = $((MAX_RETRIES * RETRY_INTERVAL))s window"
echo ""

for ep in "${ENDPOINTS[@]}"; do
  check_endpoint "$ep"
done

echo ""

# --- Final summary ----------------------------------------------------------
if [[ "$OVERALL_PASS" == "true" ]]; then
  echo "SMOKE_RESULT status=PASS cold_start_seconds=${COLD_START_SECONDS}"
  exit 0
else
  echo "SMOKE_RESULT status=FAIL cold_start_seconds=${COLD_START_SECONDS}"
  exit 1
fi
