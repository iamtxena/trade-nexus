"""Contract-oriented smoke tests for Platform API v1 handlers."""

from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from src.main import app
from src.platform_api import router_v1
from src.platform_api.state_store import OrderRecord


HEADERS = {
    "Authorization": "Bearer test-token",
    "X-API-Key": "test-key",
    "X-Request-Id": "req-contract-001",
}


def _client() -> TestClient:
    return TestClient(app)


def test_health_and_research_routes() -> None:
    client = _client()

    health = client.get("/v1/health", headers=HEADERS)
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    market_scan = client.post(
        "/v1/research/market-scan",
        headers=HEADERS,
        json={
            "assetClasses": ["crypto", "stocks"],
            "capital": 25000,
            "constraints": {"maxPositionPct": 25, "maxDrawdownPct": 12},
        },
    )
    assert market_scan.status_code == 200
    payload = market_scan.json()
    assert payload["requestId"] == HEADERS["X-Request-Id"]
    assert len(payload["strategyIdeas"]) == 2


def test_strategy_and_backtest_routes() -> None:
    client = _client()

    list_resp = client.get("/v1/strategies", headers=HEADERS)
    assert list_resp.status_code == 200
    assert "items" in list_resp.json()

    create_resp = client.post(
        "/v1/strategies",
        headers=HEADERS,
        json={
            "name": "Mean Reversion ETH",
            "description": "Mean-reversion strategy for ETH using 20-period z-score bands.",
            "provider": "xai",
        },
    )
    assert create_resp.status_code == 201
    created_strategy = create_resp.json()["strategy"]

    strategy_id = created_strategy["id"]
    get_resp = client.get(f"/v1/strategies/{strategy_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    assert get_resp.json()["strategy"]["id"] == strategy_id

    patch_resp = client.patch(
        f"/v1/strategies/{strategy_id}",
        headers=HEADERS,
        json={"status": "deployable", "tags": ["momentum", "approved"]},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["strategy"]["status"] == "deployable"

    create_backtest = client.post(
        f"/v1/strategies/{strategy_id}/backtests",
        headers=HEADERS,
        json={
            "dataIds": ["dataset-btc-1h-2025"],
            "startDate": "2025-01-01",
            "endDate": "2025-12-31",
            "initialCash": 100000,
        },
    )
    assert create_backtest.status_code == 202
    backtest_id = create_backtest.json()["backtest"]["id"]

    get_backtest = client.get(f"/v1/backtests/{backtest_id}", headers=HEADERS)
    assert get_backtest.status_code == 200
    assert get_backtest.json()["backtest"]["id"] == backtest_id


def test_backtest_request_rejects_empty_data_id_lists() -> None:
    client = _client()

    create_resp = client.post(
        "/v1/strategies",
        headers=HEADERS,
        json={
            "name": "Backtest Validation Strategy",
            "description": "Strategy used to validate CreateBacktestRequest constraints.",
            "provider": "xai",
        },
    )
    assert create_resp.status_code == 201
    strategy_id = create_resp.json()["strategy"]["id"]

    empty_data_ids = client.post(
        f"/v1/strategies/{strategy_id}/backtests",
        headers=HEADERS,
        json={
            "dataIds": [],
            "startDate": "2025-01-01",
            "endDate": "2025-12-31",
            "initialCash": 100000,
        },
    )
    assert empty_data_ids.status_code == 422

    empty_with_dataset_ids = client.post(
        f"/v1/strategies/{strategy_id}/backtests",
        headers=HEADERS,
        json={
            "dataIds": [],
            "datasetIds": ["dataset-btc-1h-2025"],
            "startDate": "2025-01-01",
            "endDate": "2025-12-31",
            "initialCash": 100000,
        },
    )
    assert empty_with_dataset_ids.status_code == 422


def test_execution_routes_and_idempotency() -> None:
    client = _client()

    deployments = client.get("/v1/deployments", headers=HEADERS)
    assert deployments.status_code == 200

    deployment_payload = {
        "strategyId": "strat-001",
        "mode": "paper",
        "capital": 20000,
    }
    create_deployment = client.post(
        "/v1/deployments",
        headers={**HEADERS, "Idempotency-Key": "idem-deploy-001"},
        json=deployment_payload,
    )
    assert create_deployment.status_code == 202
    deployment = create_deployment.json()["deployment"]

    replay = client.post(
        "/v1/deployments",
        headers={**HEADERS, "Idempotency-Key": "idem-deploy-001"},
        json=deployment_payload,
    )
    assert replay.status_code == 202
    assert replay.json()["deployment"]["id"] == deployment["id"]

    conflict = client.post(
        "/v1/deployments",
        headers={**HEADERS, "Idempotency-Key": "idem-deploy-001"},
        json={"strategyId": "strat-001", "mode": "paper", "capital": 21000},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"

    deployment_id = deployment["id"]
    get_deployment = client.get(f"/v1/deployments/{deployment_id}", headers=HEADERS)
    assert get_deployment.status_code == 200

    stop_deployment = client.post(
        f"/v1/deployments/{deployment_id}/actions/stop",
        headers=HEADERS,
        json={"reason": "Risk policy drawdown threshold breached."},
    )
    assert stop_deployment.status_code == 202
    assert stop_deployment.json()["deployment"]["status"] == "stopping"

    list_portfolios = client.get("/v1/portfolios", headers=HEADERS)
    assert list_portfolios.status_code == 200

    get_portfolio = client.get("/v1/portfolios/portfolio-paper-001", headers=HEADERS)
    assert get_portfolio.status_code == 200

    list_orders = client.get("/v1/orders", headers=HEADERS)
    assert list_orders.status_code == 200

    create_order_payload = {
        "symbol": "BTCUSDT",
        "side": "buy",
        "type": "limit",
        "quantity": 0.1,
        "price": 64500,
        "deploymentId": deployment_id,
    }
    create_order = client.post(
        "/v1/orders",
        headers={**HEADERS, "Idempotency-Key": "idem-order-001"},
        json=create_order_payload,
    )
    assert create_order.status_code == 201
    order = create_order.json()["order"]

    replay_order = client.post(
        "/v1/orders",
        headers={**HEADERS, "Idempotency-Key": "idem-order-001"},
        json=create_order_payload,
    )
    assert replay_order.status_code == 201
    assert replay_order.json()["order"]["id"] == order["id"]

    order_conflict = client.post(
        "/v1/orders",
        headers={**HEADERS, "Idempotency-Key": "idem-order-001"},
        json={**create_order_payload, "quantity": 0.2},
    )
    assert order_conflict.status_code == 409

    order_id = order["id"]
    get_order = client.get(f"/v1/orders/{order_id}", headers=HEADERS)
    assert get_order.status_code == 200

    cancel_order = client.delete(f"/v1/orders/{order_id}", headers=HEADERS)
    assert cancel_order.status_code == 200
    assert cancel_order.json()["order"]["status"] == "cancelled"


def test_create_deployment_returns_risk_limit_breach_error() -> None:
    client = _client()
    response = client.post(
        "/v1/deployments",
        headers={**HEADERS, "Idempotency-Key": "idem-risk-deploy-422-001"},
        json={
            "strategyId": "strat-001",
            "mode": "paper",
            "capital": 1_000_001,
        },
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["requestId"] == HEADERS["X-Request-Id"]
    assert payload["error"]["code"] == "RISK_LIMIT_BREACH"


def test_create_deployment_returns_kill_switch_active_error() -> None:
    client = _client()
    original_policy = copy.deepcopy(router_v1._store.risk_policy)
    try:
        router_v1._store.risk_policy["killSwitch"]["triggered"] = True
        response = client.post(
            "/v1/deployments",
            headers={**HEADERS, "Idempotency-Key": "idem-risk-deploy-423-001"},
            json={
                "strategyId": "strat-001",
                "mode": "paper",
                "capital": 20_000,
            },
        )
    finally:
        router_v1._store.risk_policy = original_policy

    assert response.status_code == 423
    payload = response.json()
    assert payload["requestId"] == HEADERS["X-Request-Id"]
    assert payload["error"]["code"] == "RISK_KILL_SWITCH_ACTIVE"


def test_create_order_returns_risk_limit_breach_error() -> None:
    client = _client()
    response = client.post(
        "/v1/orders",
        headers={**HEADERS, "Idempotency-Key": "idem-risk-order-422-001"},
        json={
            "symbol": "BTCUSDT",
            "side": "buy",
            "type": "limit",
            "quantity": 20.0,
            "price": 100_000.0,
            "deploymentId": "dep-001",
        },
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["requestId"] == HEADERS["X-Request-Id"]
    assert payload["error"]["code"] == "RISK_LIMIT_BREACH"


def test_create_order_returns_kill_switch_active_error() -> None:
    client = _client()
    original_policy = copy.deepcopy(router_v1._store.risk_policy)
    try:
        router_v1._store.risk_policy["killSwitch"]["triggered"] = True
        response = client.post(
            "/v1/orders",
            headers={**HEADERS, "Idempotency-Key": "idem-risk-order-423-001"},
            json={
                "symbol": "BTCUSDT",
                "side": "buy",
                "type": "limit",
                "quantity": 0.1,
                "price": 64_500,
                "deploymentId": "dep-001",
            },
        )
    finally:
        router_v1._store.risk_policy = original_policy

    assert response.status_code == 423
    payload = response.json()
    assert payload["requestId"] == HEADERS["X-Request-Id"]
    assert payload["error"]["code"] == "RISK_KILL_SWITCH_ACTIVE"


def test_dataset_routes_and_dataset_ref_backtests() -> None:
    client = _client()

    init_resp = client.post(
        "/v1/datasets/uploads:init",
        headers=HEADERS,
        json={
            "filename": "btc.csv",
            "contentType": "text/csv",
            "sizeBytes": 2048,
        },
    )
    assert init_resp.status_code == 202
    dataset_id = init_resp.json()["datasetId"]

    complete_resp = client.post(
        f"/v1/datasets/{dataset_id}/uploads:complete",
        headers=HEADERS,
    )
    assert complete_resp.status_code == 202

    validate_resp = client.post(
        f"/v1/datasets/{dataset_id}/validate",
        headers=HEADERS,
    )
    assert validate_resp.status_code == 202

    transform_resp = client.post(
        f"/v1/datasets/{dataset_id}/transform/candles",
        headers=HEADERS,
        json={"frequency": "1h"},
    )
    assert transform_resp.status_code == 202

    publish_resp = client.post(
        f"/v1/datasets/{dataset_id}/publish/lona",
        headers=HEADERS,
    )
    assert publish_resp.status_code == 202
    assert publish_resp.json()["dataset"]["status"] == "published_lona"

    list_resp = client.get("/v1/datasets", headers=HEADERS)
    assert list_resp.status_code == 200

    get_resp = client.get(f"/v1/datasets/{dataset_id}", headers=HEADERS)
    assert get_resp.status_code == 200

    report_resp = client.get(f"/v1/datasets/{dataset_id}/quality-report", headers=HEADERS)
    assert report_resp.status_code == 200

    create_strategy = client.post(
        "/v1/strategies",
        headers=HEADERS,
        json={
            "name": "Dataset Ref Strategy",
            "description": "Dataset reference strategy for thin slice backtest flow.",
            "provider": "xai",
        },
    )
    assert create_strategy.status_code == 201
    strategy_id = create_strategy.json()["strategy"]["id"]

    dataset_backtest = client.post(
        f"/v1/strategies/{strategy_id}/backtests",
        headers=HEADERS,
        json={
            "datasetIds": [dataset_id],
            "startDate": "2025-01-01",
            "endDate": "2025-12-31",
            "initialCash": 100000,
        },
    )
    assert dataset_backtest.status_code == 202

    unresolved = client.post(
        f"/v1/strategies/{strategy_id}/backtests",
        headers=HEADERS,
        json={
            "datasetIds": ["dataset-missing-999"],
            "startDate": "2025-01-01",
            "endDate": "2025-12-31",
            "initialCash": 100000,
        },
    )
    assert unresolved.status_code == 404
    assert unresolved.json()["error"]["code"] in {"DATASET_NOT_PUBLISHED", "DATASET_NOT_FOUND"}


def test_stop_deployment_uses_adapter_failure_status(monkeypatch) -> None:
    client = _client()

    create_strategy = client.post(
        "/v1/strategies",
        headers=HEADERS,
        json={
            "name": "Stop Failure Strategy",
            "description": "Exercise deployment stop status mapping.",
            "provider": "xai",
        },
    )
    assert create_strategy.status_code == 201
    strategy_id = create_strategy.json()["strategy"]["id"]

    create_deployment = client.post(
        "/v1/deployments",
        headers={**HEADERS, "Idempotency-Key": "idem-stop-status-001"},
        json={"strategyId": strategy_id, "mode": "paper", "capital": 12000},
    )
    assert create_deployment.status_code == 202
    deployment_id = create_deployment.json()["deployment"]["id"]

    async def _stop_failed(**_: object) -> dict[str, str]:
        return {"status": "failed"}

    monkeypatch.setattr(router_v1._execution_adapter, "stop_deployment", _stop_failed)

    stop_response = client.post(
        f"/v1/deployments/{deployment_id}/actions/stop",
        headers=HEADERS,
    )
    assert stop_response.status_code == 202
    assert stop_response.json()["deployment"]["status"] == "failed"


def test_cancel_order_maps_unknown_provider_status_to_failed(monkeypatch) -> None:
    client = _client()
    create_order = client.post(
        "/v1/orders",
        headers={**HEADERS, "Idempotency-Key": "idem-order-map-001"},
        json={
            "symbol": "BTCUSDT",
            "side": "buy",
            "type": "limit",
            "quantity": 0.1,
            "price": 64500,
            "deploymentId": "dep-001",
        },
    )
    assert create_order.status_code == 201
    order_id = create_order.json()["order"]["id"]

    async def _cancel_unknown(**_: object) -> dict[str, str]:
        return {"status": "processing"}

    monkeypatch.setattr(router_v1._execution_adapter, "cancel_order", _cancel_unknown)

    cancel_response = client.delete(f"/v1/orders/{order_id}", headers=HEADERS)
    assert cancel_response.status_code == 200
    assert cancel_response.json()["order"]["status"] == "failed"


def test_create_order_maps_provider_status_for_existing_store_record(monkeypatch) -> None:
    client = _client()

    async def _place_order_existing(**_: object) -> dict[str, str]:
        order_id = "ord-existing-001"
        router_v1._store.orders[order_id] = OrderRecord(
            id=order_id,
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            quantity=0.1,
            price=64500,
            status="pending",
            deployment_id="dep-001",
            provider_order_id="live-order-existing-001",
        )
        return {"orderId": order_id, "providerOrderId": "live-order-existing-001", "status": "processing"}

    monkeypatch.setattr(router_v1._execution_adapter, "place_order", _place_order_existing)

    create_order = client.post(
        "/v1/orders",
        headers={**HEADERS, "Idempotency-Key": "idem-order-existing-map-001"},
        json={
            "symbol": "BTCUSDT",
            "side": "buy",
            "type": "limit",
            "quantity": 0.1,
            "price": 64500,
            "deploymentId": "dep-001",
        },
    )
    assert create_order.status_code == 201
    assert create_order.json()["order"]["status"] == "failed"
