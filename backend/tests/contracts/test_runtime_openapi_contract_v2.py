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
