"""Thin-bridge backtest flow tests using dataset references."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.main import app


HEADERS = {
    "Authorization": "Bearer test-token",
    "X-API-Key": "test-key",
    "X-Request-Id": "req-dataset-bridge-001",
}


def test_backtest_accepts_dataset_refs_when_dataset_is_published() -> None:
    client = TestClient(app)

    create_strategy = client.post(
        "/v1/strategies",
        headers=HEADERS,
        json={
            "name": "Dataset Bridge Strategy",
            "description": "Dataset bridge strategy for Gate2 thin-slice integration test.",
            "provider": "xai",
        },
    )
    assert create_strategy.status_code == 201
    strategy_id = create_strategy.json()["strategy"]["id"]

    create_backtest = client.post(
        f"/v1/strategies/{strategy_id}/backtests",
        headers=HEADERS,
        json={
            "datasetIds": ["dataset-btc-1h-2025"],
            "startDate": "2025-01-01",
            "endDate": "2025-12-31",
            "initialCash": 100000,
        },
    )
    assert create_backtest.status_code == 202
    body = create_backtest.json()
    assert body["backtest"]["status"] in {"queued", "running", "completed"}


def test_backtest_dataset_refs_fail_with_typed_error_when_unresolved() -> None:
    client = TestClient(app)

    create_strategy = client.post(
        "/v1/strategies",
        headers=HEADERS,
        json={
            "name": "Dataset Missing Strategy",
            "description": "Dataset bridge error path strategy for unresolved dataset references.",
            "provider": "xai",
        },
    )
    assert create_strategy.status_code == 201
    strategy_id = create_strategy.json()["strategy"]["id"]

    create_backtest = client.post(
        f"/v1/strategies/{strategy_id}/backtests",
        headers=HEADERS,
        json={
            "datasetIds": ["dataset-does-not-exist"],
            "startDate": "2025-01-01",
            "endDate": "2025-12-31",
            "initialCash": 100000,
        },
    )
    assert create_backtest.status_code == 404
    payload = create_backtest.json()
    assert payload["error"]["code"] in {"DATASET_NOT_PUBLISHED", "DATASET_NOT_FOUND"}
    assert payload["requestId"] == HEADERS["X-Request-Id"]
