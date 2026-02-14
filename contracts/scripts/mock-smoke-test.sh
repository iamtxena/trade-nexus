#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
FIXTURES_DIR="${REPO_ROOT}/contracts/fixtures"
PORT="${PRISM_PORT:-4010}"
HOST="${PRISM_HOST:-127.0.0.1}"
BASE_URL="http://${HOST}:${PORT}"

PRISM_PID=""
cleanup() {
  if [[ -n "${PRISM_PID}" ]] && kill -0 "${PRISM_PID}" >/dev/null 2>&1; then
    kill "${PRISM_PID}" >/dev/null 2>&1 || true
    wait "${PRISM_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

"${SCRIPT_DIR}/run-mock-server.sh" >/tmp/trade-nexus-prism.log 2>&1 &
PRISM_PID=$!

for _ in {1..30}; do
  if curl -sS -o /dev/null "${BASE_URL}/v1/health"; then
    break
  fi
  sleep 1
done

request_and_assert() {
  local method="$1"
  local path="$2"
  local expected_status="$3"
  local body_file="${4:-}"
  local idempotency_key="${5:-}"

  local response_file
  response_file="$(mktemp /tmp/prism-smoke-response.XXXXXX)"

  local -a curl_args=(
    -sS
    -o "${response_file}"
    -w "%{http_code}"
    -X "${method}"
    -H "Authorization: Bearer mock-token"
    -H "X-API-Key: mock-api-key"
    -H "X-Request-Id: req-smoke-001"
  )

  if [[ -n "${idempotency_key}" ]]; then
    curl_args+=(-H "Idempotency-Key: ${idempotency_key}")
  fi

  if [[ -n "${body_file}" ]]; then
    curl_args+=(
      -H "Content-Type: application/json"
      --data "@${body_file}"
    )
  fi

  local actual_status
  actual_status="$(curl "${curl_args[@]}" "${BASE_URL}${path}")"

  if [[ "${actual_status}" == "404" || "${actual_status}" == "405" ]]; then
    echo "Routing failure for ${method} ${path}: HTTP ${actual_status}" >&2
    cat "${response_file}" >&2
    rm -f "${response_file}"
    exit 1
  fi

  if [[ "${actual_status}" != "${expected_status}" ]]; then
    echo "Unexpected status for ${method} ${path}: expected ${expected_status}, got ${actual_status}" >&2
    cat "${response_file}" >&2
    rm -f "${response_file}"
    exit 1
  fi

  rm -f "${response_file}"
}

request_and_capture_field() {
  local method="$1"
  local path="$2"
  local expected_status="$3"
  local body_file="${4:-}"
  local idempotency_key="${5:-}"
  local field_name="$6"

  local response_file
  response_file="$(mktemp /tmp/prism-smoke-response.XXXXXX)"

  local -a curl_args=(
    -sS
    -o "${response_file}"
    -w "%{http_code}"
    -X "${method}"
    -H "Authorization: Bearer mock-token"
    -H "X-API-Key: mock-api-key"
    -H "X-Request-Id: req-smoke-001"
  )

  if [[ -n "${idempotency_key}" ]]; then
    curl_args+=(-H "Idempotency-Key: ${idempotency_key}")
  fi

  if [[ -n "${body_file}" ]]; then
    curl_args+=(
      -H "Content-Type: application/json"
      --data "@${body_file}"
    )
  fi

  local actual_status
  actual_status="$(curl "${curl_args[@]}" "${BASE_URL}${path}")"
  if [[ "${actual_status}" != "${expected_status}" ]]; then
    echo "Unexpected status for ${method} ${path}: expected ${expected_status}, got ${actual_status}" >&2
    cat "${response_file}" >&2
    rm -f "${response_file}"
    exit 1
  fi

  local value
  value="$(python3 - "${response_file}" "${field_name}" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
field_name = sys.argv[2]
value = payload.get(field_name)
if value is None:
    raise SystemExit(1)
print(value)
PY
)"
  rm -f "${response_file}"
  echo "${value}"
}

request_and_assert "GET" "/v1/health" "200"
request_and_assert "POST" "/v1/research/market-scan" "200" "${FIXTURES_DIR}/market-scan.request.json"
request_and_assert "GET" "/v1/strategies" "200"
request_and_assert "POST" "/v1/strategies" "201" "${FIXTURES_DIR}/create-strategy.request.json"
request_and_assert "GET" "/v1/strategies/strat-001" "200"
request_and_assert "PATCH" "/v1/strategies/strat-001" "200" "${FIXTURES_DIR}/update-strategy.request.json"
request_and_assert "POST" "/v1/strategies/strat-001/backtests" "202" "${FIXTURES_DIR}/create-backtest.request.json"
request_and_assert "GET" "/v1/backtests/bt-001" "200"
request_and_assert "GET" "/v1/deployments" "200"
request_and_assert "POST" "/v1/deployments" "202" "${FIXTURES_DIR}/create-deployment.request.json" "idem-deploy-001"
request_and_assert "GET" "/v1/deployments/dep-001" "200"
request_and_assert "POST" "/v1/deployments/dep-001/actions/stop" "202" "${FIXTURES_DIR}/stop-deployment.request.json"
request_and_assert "GET" "/v1/portfolios" "200"
request_and_assert "GET" "/v1/portfolios/portfolio-paper-001" "200"
request_and_assert "GET" "/v1/orders" "200"
request_and_assert "POST" "/v1/orders" "201" "${FIXTURES_DIR}/create-order.request.json" "idem-order-001"
request_and_assert "GET" "/v1/orders/ord-001" "200"
request_and_assert "DELETE" "/v1/orders/ord-001" "200"
dataset_id="$(request_and_capture_field \
  "POST" \
  "/v1/datasets/uploads:init" \
  "202" \
  "${FIXTURES_DIR}/dataset-upload-init.request.json" \
  "" \
  "datasetId"
)"
request_and_assert "POST" "/v1/datasets/${dataset_id}/uploads:complete" "202" "${FIXTURES_DIR}/dataset-upload-complete.request.json"
request_and_assert "POST" "/v1/datasets/${dataset_id}/validate" "202" "${FIXTURES_DIR}/dataset-validate.request.json"
request_and_assert "POST" "/v1/datasets/${dataset_id}/transform/candles" "202" "${FIXTURES_DIR}/dataset-transform-candles.request.json"
request_and_assert "POST" "/v1/datasets/${dataset_id}/publish/lona" "202" "${FIXTURES_DIR}/dataset-publish-lona.request.json"
request_and_assert "GET" "/v1/datasets" "200"
request_and_assert "GET" "/v1/datasets/${dataset_id}" "200"
request_and_assert "GET" "/v1/datasets/${dataset_id}/quality-report" "200"

echo "Mock smoke tests passed for all v1 operations."
