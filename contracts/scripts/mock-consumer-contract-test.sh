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

for _ in {1..90}; do
  if curl -fsS -o /dev/null "${BASE_URL}/v1/health"; then
    break
  fi
  sleep 1
done

if ! curl -fsS -o /dev/null "${BASE_URL}/v1/health"; then
  echo "Prism mock server failed to become ready on ${BASE_URL}." >&2
  if [[ -f /tmp/trade-nexus-prism.log ]]; then
    echo "--- prism log start ---" >&2
    cat /tmp/trade-nexus-prism.log >&2 || true
    echo "--- prism log end ---" >&2
  fi
  exit 1
fi

python3 - "${BASE_URL}" "${FIXTURES_DIR}" <<'PY'
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path


BASE_URL = sys.argv[1].rstrip("/")
FIXTURES_DIR = Path(sys.argv[2])


def request(method: str, path: str, *, body: dict | None = None) -> tuple[int, dict]:
    payload: bytes | None = None
    headers = {
        "Authorization": "Bearer mock-token",
        "X-API-Key": "mock-api-key",
        "X-Request-Id": "req-consumer-mock-001",
    }
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=payload,
        method=method,
        headers=headers,
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.getcode()
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        parsed = json.loads(raw) if raw else {}
        return exc.code, parsed


def assert_non_empty_str(payload: dict, field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AssertionError(f"Expected non-empty string field '{field}', got: {value!r}")
    return value


# Trading CLI consumer expectations: research + strategies endpoints.
market_scan_request = json.loads((FIXTURES_DIR / "market-scan.request.json").read_text(encoding="utf-8"))
status, market_scan_payload = request("POST", "/v1/research/market-scan", body=market_scan_request)
if status != 200:
    raise AssertionError(f"/v1/research/market-scan expected 200, got {status}: {market_scan_payload}")
assert_non_empty_str(market_scan_payload, "requestId")
strategy_ideas = market_scan_payload.get("strategyIdeas")
if not isinstance(strategy_ideas, list):
    raise AssertionError(f"Expected strategyIdeas list, got: {strategy_ideas!r}")

status, strategies_payload = request("GET", "/v1/strategies")
if status != 200:
    raise AssertionError(f"/v1/strategies expected 200, got {status}: {strategies_payload}")
assert_non_empty_str(strategies_payload, "requestId")
items = strategies_payload.get("items")
if not isinstance(items, list):
    raise AssertionError(f"Expected items list, got: {items!r}")

# OpenClaw consumer expectations: v2 conversation session + turn workflow.
status, create_session_payload = request(
    "POST",
    "/v2/conversations/sessions",
    body={
        "channel": "openclaw",
        "topic": "consumer mock contract test",
        "metadata": {"source": "openclaw"},
    },
)
if status != 201:
    raise AssertionError(f"/v2/conversations/sessions expected 201, got {status}: {create_session_payload}")
assert_non_empty_str(create_session_payload, "requestId")
session = create_session_payload.get("session")
if not isinstance(session, dict):
    raise AssertionError(f"Expected session object, got: {session!r}")
session_id = assert_non_empty_str(session, "id")
channel = session.get("channel")
if not isinstance(channel, str):
    raise AssertionError(f"Expected session.channel string, got: {channel!r}")

status, create_turn_payload = request(
    "POST",
    f"/v2/conversations/sessions/{session_id}/turns",
    body={
        "role": "user",
        "message": "scan and deploy",
        "metadata": {"source": "openclaw"},
    },
)
if status != 201:
    raise AssertionError(
        f"/v2/conversations/sessions/{{sessionId}}/turns expected 201, got {status}: {create_turn_payload}"
    )
assert_non_empty_str(create_turn_payload, "requestId")
assert_non_empty_str(create_turn_payload, "sessionId")
turn = create_turn_payload.get("turn")
if not isinstance(turn, dict):
    raise AssertionError(f"Expected turn object, got: {turn!r}")
assert_non_empty_str(turn, "id")
assert_non_empty_str(turn, "sessionId")

print("Consumer mock contract checks passed.")
PY
