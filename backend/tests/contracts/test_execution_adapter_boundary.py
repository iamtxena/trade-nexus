"""Boundary tests for execution adapter baseline."""

from __future__ import annotations

import asyncio

from src.platform_api.adapters.execution_adapter import InMemoryExecutionAdapter
from src.platform_api.state_store import InMemoryStateStore


async def _run_execution_adapter_deployment_and_order_contracts() -> None:
    store = InMemoryStateStore()
    adapter = InMemoryExecutionAdapter(store)

    deployment = await adapter.create_deployment(
        strategy_id="strat-001",
        mode="paper",
        capital=10000,
        tenant_id="tenant-a",
        user_id="user-a",
        idempotency_key="idem-1",
    )
    assert deployment["status"] in {"queued", "running"}

    provider_deployment_id = str(deployment["providerDeploymentId"])
    get_deployment = await adapter.get_deployment(
        provider_deployment_id=provider_deployment_id,
        tenant_id="tenant-a",
        user_id="user-a",
    )
    assert get_deployment["status"] in {"queued", "running", "paused", "stopping", "stopped", "failed"}

    stop_deployment = await adapter.stop_deployment(
        provider_deployment_id=provider_deployment_id,
        reason="manual",
        tenant_id="tenant-a",
        user_id="user-a",
    )
    assert stop_deployment["status"] in {"stopping", "stopped", "failed"}

    order = await adapter.place_order(
        symbol="BTCUSDT",
        side="buy",
        order_type="limit",
        quantity=0.1,
        price=64000,
        deployment_id=str(deployment["deploymentId"]),
        tenant_id="tenant-a",
        user_id="user-a",
        idempotency_key="idem-2",
    )
    assert order["status"] in {"pending", "filled"}

    provider_order_id = str(order["providerOrderId"])
    cancel = await adapter.cancel_order(
        provider_order_id=provider_order_id,
        tenant_id="tenant-a",
        user_id="user-a",
    )
    assert cancel["status"] in {"cancelled", "failed"}


async def _run_execution_adapter_portfolio_contracts() -> None:
    store = InMemoryStateStore()
    adapter = InMemoryExecutionAdapter(store)

    portfolios = await adapter.list_portfolios()
    assert len(portfolios) >= 1

    snapshot = await adapter.get_portfolio_snapshot(
        portfolio_id=portfolios[0].id,
        tenant_id="tenant-a",
        user_id="user-a",
    )
    assert snapshot is not None
    assert snapshot.cash >= 0


def test_execution_adapter_deployment_and_order_contracts() -> None:
    asyncio.run(_run_execution_adapter_deployment_and_order_contracts())


def test_execution_adapter_portfolio_contracts() -> None:
    asyncio.run(_run_execution_adapter_portfolio_contracts())
