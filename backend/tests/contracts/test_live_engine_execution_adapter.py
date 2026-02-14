"""Contract tests for live-engine-backed execution adapter parsing."""

from __future__ import annotations

import asyncio

from src.platform_api.adapters.execution_adapter import LiveEngineExecutionAdapter


async def _run_adapter_contract() -> None:
    adapter = LiveEngineExecutionAdapter(
        base_url="http://live-engine.local",
        service_api_key="service-key",
    )

    async def fake_request(**kwargs):  # type: ignore[no-untyped-def]
        path = kwargs["path"]
        if path == "/api/internal/deployments" and kwargs["method"] == "POST":
            return {
                "deployment": {
                    "id": "dep-123",
                    "strategyId": "strat-001",
                    "mode": "paper",
                    "status": "queued",
                    "capital": 10000,
                    "providerRefId": "live-dep-123",
                    "latestPnl": None,
                    "createdAt": "2026-02-14T10:00:00Z",
                    "updatedAt": "2026-02-14T10:00:00Z",
                }
            }
        if path == "/api/internal/deployments/live-dep-123" and kwargs["method"] == "GET":
            return {"deployment": {"id": "dep-123", "status": "running", "latestPnl": 12.5}}
        if path.startswith("/api/internal/orders") and kwargs["method"] == "POST":
            return {
                "order": {
                    "id": "ord-123",
                    "providerOrderId": "live-order-123",
                    "symbol": "BTCUSDT",
                    "side": "buy",
                    "type": "market",
                    "quantity": 0.1,
                    "price": None,
                    "status": "pending",
                    "deploymentId": "dep-123",
                    "createdAt": "2026-02-14T10:00:01Z",
                }
            }
        if path == "/api/internal/orders/live-order-123" and kwargs["method"] == "GET":
            return {
                "order": {
                    "id": "ord-123",
                    "providerOrderId": "live-order-123",
                    "symbol": "BTCUSDT",
                    "side": "buy",
                    "type": "market",
                    "quantity": 0.1,
                    "price": None,
                    "status": "filled",
                    "deploymentId": "dep-123",
                    "createdAt": "2026-02-14T10:00:01Z",
                }
            }
        if path == "/api/internal/portfolios/portfolio-paper-001":
            return {
                "portfolio": {
                    "id": "portfolio-paper-001",
                    "mode": "paper",
                    "cash": 1000,
                    "totalValue": 1100,
                    "pnlTotal": 100,
                    "positions": [],
                }
            }
        return {"items": []}

    adapter._request = fake_request  # type: ignore[assignment]

    deployment = await adapter.create_deployment(
        strategy_id="strat-001",
        mode="paper",
        capital=10000,
        tenant_id="tenant-a",
        user_id="user-a",
        idempotency_key="idem-1",
    )
    assert deployment["deploymentId"] == "dep-123"
    assert deployment["providerDeploymentId"] == "live-dep-123"

    deployment_state = await adapter.get_deployment(
        provider_deployment_id="live-dep-123",
        tenant_id="tenant-a",
        user_id="user-a",
    )
    assert deployment_state["status"] == "running"

    order = await adapter.place_order(
        symbol="BTCUSDT",
        side="buy",
        order_type="market",
        quantity=0.1,
        price=None,
        deployment_id="dep-123",
        tenant_id="tenant-a",
        user_id="user-a",
        idempotency_key="idem-2",
    )
    assert order["providerOrderId"] == "live-order-123"

    provider_order = await adapter.get_order(
        provider_order_id="live-order-123",
        tenant_id="tenant-a",
        user_id="user-a",
    )
    assert provider_order is not None
    assert provider_order.status == "filled"

    portfolio = await adapter.get_portfolio_snapshot(
        portfolio_id="portfolio-paper-001",
        tenant_id="tenant-a",
        user_id="user-a",
    )
    assert portfolio is not None
    assert portfolio.total_value == 1100


def test_live_engine_execution_adapter_contract() -> None:
    asyncio.run(_run_adapter_contract())
