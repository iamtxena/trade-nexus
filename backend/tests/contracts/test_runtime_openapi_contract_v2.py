"""Runtime contract checks for OpenAPI-backed v2 handlers."""

from __future__ import annotations

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.main import app


HEADERS = {
    "Authorization": "Bearer test-token",
    "X-API-Key": "test-key",
    "X-Request-Id": "req-runtime-v2-001",
}


def test_openapi_v2_routes_are_registered() -> None:
    expected = {
        ("POST", "/v2/knowledge/search"),
        ("GET", "/v2/knowledge/patterns"),
        ("GET", "/v2/knowledge/regimes/{asset}"),
        ("POST", "/v2/data/exports/backtest"),
        ("GET", "/v2/data/exports/{exportId}"),
        ("POST", "/v2/research/market-scan"),
        ("POST", "/v2/conversations/sessions"),
        ("GET", "/v2/conversations/sessions/{sessionId}"),
        ("POST", "/v2/conversations/sessions/{sessionId}/turns"),
        ("POST", "/v2/validation-runs"),
        ("GET", "/v2/validation-runs/{runId}"),
        ("GET", "/v2/validation-runs/{runId}/artifact"),
        ("POST", "/v2/validation-runs/{runId}/review"),
        ("POST", "/v2/validation-runs/{runId}/render"),
        ("POST", "/v2/validation-baselines"),
        ("POST", "/v2/validation-regressions/replay"),
    }
    found: set[tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            found.add((method, route.path))
    missing = expected - found
    assert not missing, f"Missing runtime v2 routes: {missing}"


def test_openapi_v2_runtime_status_codes() -> None:
    client = TestClient(app)

    assert (
        client.post(
            "/v2/knowledge/search",
            headers=HEADERS,
            json={"query": "momentum", "assets": ["BTCUSDT"], "limit": 3},
        ).status_code
        == 200
    )
    assert client.get("/v2/knowledge/patterns", headers=HEADERS).status_code == 200
    assert client.get("/v2/knowledge/regimes/BTCUSDT", headers=HEADERS).status_code == 200

    create_export = client.post(
        "/v2/data/exports/backtest",
        headers=HEADERS,
        json={"datasetIds": ["dataset-btc-1h-2025"], "assetClasses": ["crypto"]},
    )
    assert create_export.status_code == 202
    export_id = create_export.json()["export"]["id"]

    assert client.get(f"/v2/data/exports/{export_id}", headers=HEADERS).status_code == 200
    assert (
        client.post(
            "/v2/research/market-scan",
            headers=HEADERS,
            json={"assetClasses": ["crypto"], "capital": 25000},
        ).status_code
        == 200
    )

    create_session = client.post(
        "/v2/conversations/sessions",
        headers=HEADERS,
        json={"channel": "openclaw", "topic": "swing-trading"},
    )
    assert create_session.status_code == 201
    session_id = create_session.json()["session"]["id"]

    assert client.get(f"/v2/conversations/sessions/{session_id}", headers=HEADERS).status_code == 200
    assert (
        client.post(
            f"/v2/conversations/sessions/{session_id}/turns",
            headers=HEADERS,
            json={"role": "user", "message": "deploy my strategy after backtest"},
        ).status_code
        == 201
    )

    create_run = client.post(
        "/v2/validation-runs",
        headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-validation-run-001"},
        json={
            "strategyId": "strat-001",
            "providerRefId": "lona-strategy-123",
            "prompt": "Build zig-zag strategy for BTC 1h with trend filter",
            "requestedIndicators": ["zigzag", "ema"],
            "datasetIds": ["dataset-btc-1h-2025"],
            "backtestReportRef": "blob://validation/candidate/backtest-report.json",
            "policy": {
                "profile": "STANDARD",
                "blockMergeOnFail": True,
                "blockReleaseOnFail": True,
                "blockMergeOnAgentFail": True,
                "blockReleaseOnAgentFail": False,
                "requireTraderReview": False,
                "hardFailOnMissingIndicators": True,
                "failClosedOnEvidenceUnavailable": True,
            },
        },
    )
    assert create_run.status_code == 202
    run_id = create_run.json()["run"]["id"]

    assert client.get(f"/v2/validation-runs/{run_id}", headers=HEADERS).status_code == 200
    assert client.get(f"/v2/validation-runs/{run_id}/artifact", headers=HEADERS).status_code == 200

    assert (
        client.post(
            f"/v2/validation-runs/{run_id}/review",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-validation-review-001"},
            json={
                "reviewerType": "agent",
                "decision": "pass",
                "summary": "Indicator fidelity and metric checks are within policy tolerance.",
                "findings": [],
                "comments": [],
            },
        ).status_code
        == 202
    )
    assert (
        client.post(
            f"/v2/validation-runs/{run_id}/render",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-validation-render-001"},
            json={"format": "html"},
        ).status_code
        == 202
    )

    create_baseline = client.post(
        "/v2/validation-baselines",
        headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-validation-baseline-001"},
        json={
            "runId": run_id,
            "name": "runtime-v2-validation-baseline",
            "notes": "Contract coverage baseline.",
        },
    )
    assert create_baseline.status_code == 201
    baseline_id = create_baseline.json()["baseline"]["id"]

    assert (
        client.post(
            "/v2/validation-regressions/replay",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-v2-validation-replay-001"},
            json={
                "baselineId": baseline_id,
                "candidateRunId": run_id,
            },
        ).status_code
        == 202
    )
