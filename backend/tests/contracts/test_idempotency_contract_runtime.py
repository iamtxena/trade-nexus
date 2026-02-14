"""Runtime checks for idempotency contract behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.main import app


HEADERS = {
    "Authorization": "Bearer test-token",
    "X-API-Key": "test-key",
    "X-Request-Id": "req-idempotency-001",
}


def test_deployment_idempotency_key_semantics() -> None:
    client = TestClient(app)
    payload = {"strategyId": "strat-001", "mode": "paper", "capital": 12000}

    first = client.post(
        "/v1/deployments",
        headers={**HEADERS, "Idempotency-Key": "idem-deploy-contract-001"},
        json=payload,
    )
    assert first.status_code == 202

    replay = client.post(
        "/v1/deployments",
        headers={**HEADERS, "Idempotency-Key": "idem-deploy-contract-001"},
        json=payload,
    )
    assert replay.status_code == 202
    assert replay.json()["deployment"]["id"] == first.json()["deployment"]["id"]

    conflict = client.post(
        "/v1/deployments",
        headers={**HEADERS, "Idempotency-Key": "idem-deploy-contract-001"},
        json={"strategyId": "strat-001", "mode": "paper", "capital": 13000},
    )
    assert conflict.status_code == 409


def test_order_idempotency_key_semantics() -> None:
    client = TestClient(app)
    payload = {
        "symbol": "BTCUSDT",
        "side": "buy",
        "type": "limit",
        "quantity": 0.1,
        "price": 64000,
        "deploymentId": "dep-001",
    }

    first = client.post(
        "/v1/orders",
        headers={**HEADERS, "Idempotency-Key": "idem-order-contract-001"},
        json=payload,
    )
    assert first.status_code == 201

    replay = client.post(
        "/v1/orders",
        headers={**HEADERS, "Idempotency-Key": "idem-order-contract-001"},
        json=payload,
    )
    assert replay.status_code == 201
    assert replay.json()["order"]["id"] == first.json()["order"]["id"]

    conflict = client.post(
        "/v1/orders",
        headers={**HEADERS, "Idempotency-Key": "idem-order-contract-001"},
        json={**payload, "quantity": 0.5},
    )
    assert conflict.status_code == 409
