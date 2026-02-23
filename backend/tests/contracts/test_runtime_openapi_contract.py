"""Runtime contract checks for OpenAPI-backed v1 handlers."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src.main import app


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "contracts" / "fixtures"

HEADERS = {
    "Authorization": "Bearer test-token",
    "X-API-Key": "tnx.bot.runtime-contract-001.secret-001",
    "X-Request-Id": "req-runtime-contract-001",
}


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_openapi_v1_routes_are_registered() -> None:
    expected = {
        ("GET", "/v1/health"),
        ("POST", "/v1/research/market-scan"),
        ("GET", "/v1/strategies"),
        ("POST", "/v1/strategies"),
        ("GET", "/v1/strategies/{strategyId}"),
        ("PATCH", "/v1/strategies/{strategyId}"),
        ("POST", "/v1/strategies/{strategyId}/backtests"),
        ("GET", "/v1/backtests/{backtestId}"),
        ("GET", "/v1/deployments"),
        ("POST", "/v1/deployments"),
        ("GET", "/v1/deployments/{deploymentId}"),
        ("POST", "/v1/deployments/{deploymentId}/actions/stop"),
        ("GET", "/v1/portfolios"),
        ("GET", "/v1/portfolios/{portfolioId}"),
        ("GET", "/v1/orders"),
        ("POST", "/v1/orders"),
        ("GET", "/v1/orders/{orderId}"),
        ("DELETE", "/v1/orders/{orderId}"),
        ("POST", "/v1/datasets/uploads:init"),
        ("POST", "/v1/datasets/{datasetId}/uploads:complete"),
        ("POST", "/v1/datasets/{datasetId}/validate"),
        ("POST", "/v1/datasets/{datasetId}/transform/candles"),
        ("POST", "/v1/datasets/{datasetId}/publish/lona"),
        ("GET", "/v1/datasets"),
        ("GET", "/v1/datasets/{datasetId}"),
        ("GET", "/v1/datasets/{datasetId}/quality-report"),
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
    assert not missing, f"Missing runtime routes: {missing}"


def test_openapi_v1_runtime_status_codes() -> None:
    client = TestClient(app)

    assert client.get("/v1/health", headers=HEADERS).status_code == 200
    assert (
        client.post("/v1/research/market-scan", headers=HEADERS, json=_fixture("market-scan.request.json")).status_code
        == 200
    )

    assert client.get("/v1/strategies", headers=HEADERS).status_code == 200
    assert client.post("/v1/strategies", headers=HEADERS, json=_fixture("create-strategy.request.json")).status_code == 201
    assert client.get("/v1/strategies/strat-001", headers=HEADERS).status_code == 200
    assert (
        client.patch("/v1/strategies/strat-001", headers=HEADERS, json=_fixture("update-strategy.request.json")).status_code
        == 200
    )
    assert (
        client.post(
            "/v1/strategies/strat-001/backtests",
            headers=HEADERS,
            json=_fixture("create-backtest.request.json"),
        ).status_code
        == 202
    )
    assert client.get("/v1/backtests/bt-001", headers=HEADERS).status_code == 200

    assert client.get("/v1/deployments", headers=HEADERS).status_code == 200
    assert (
        client.post(
            "/v1/deployments",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-deploy-001"},
            json=_fixture("create-deployment.request.json"),
        ).status_code
        == 202
    )
    assert client.get("/v1/deployments/dep-001", headers=HEADERS).status_code == 200
    assert (
        client.post(
            "/v1/deployments/dep-001/actions/stop",
            headers=HEADERS,
            json=_fixture("stop-deployment.request.json"),
        ).status_code
        == 202
    )

    assert client.get("/v1/portfolios", headers=HEADERS).status_code == 200
    assert client.get("/v1/portfolios/portfolio-paper-001", headers=HEADERS).status_code == 200

    assert client.get("/v1/orders", headers=HEADERS).status_code == 200
    assert (
        client.post(
            "/v1/orders",
            headers={**HEADERS, "Idempotency-Key": "idem-runtime-order-001"},
            json=_fixture("create-order.request.json"),
        ).status_code
        == 201
    )
    assert client.get("/v1/orders/ord-001", headers=HEADERS).status_code == 200
    assert client.delete("/v1/orders/ord-001", headers=HEADERS).status_code == 200

    init_upload = client.post(
        "/v1/datasets/uploads:init",
        headers=HEADERS,
        json=_fixture("dataset-upload-init.request.json"),
    )
    assert init_upload.status_code == 202
    dataset_id = init_upload.json()["datasetId"]

    assert (
        client.post(
            f"/v1/datasets/{dataset_id}/uploads:complete",
            headers=HEADERS,
            json=_fixture("dataset-upload-complete.request.json"),
        ).status_code
        == 202
    )
    assert (
        client.post(
            f"/v1/datasets/{dataset_id}/validate",
            headers=HEADERS,
            json=_fixture("dataset-validate.request.json"),
        ).status_code
        == 202
    )
    assert (
        client.post(
            f"/v1/datasets/{dataset_id}/transform/candles",
            headers=HEADERS,
            json=_fixture("dataset-transform-candles.request.json"),
        ).status_code
        == 202
    )
    assert (
        client.post(
            f"/v1/datasets/{dataset_id}/publish/lona",
            headers=HEADERS,
            json=_fixture("dataset-publish-lona.request.json"),
        ).status_code
        == 202
    )

    assert client.get("/v1/datasets", headers=HEADERS).status_code == 200
    assert client.get(f"/v1/datasets/{dataset_id}", headers=HEADERS).status_code == 200
    assert client.get(f"/v1/datasets/{dataset_id}/quality-report", headers=HEADERS).status_code == 200
