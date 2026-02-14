"""Tests for deployment/order reconciliation drift checks."""

from __future__ import annotations

import asyncio
from copy import deepcopy

from src.platform_api.state_store import DeploymentRecord, InMemoryStateStore, OrderRecord
from src.platform_api.services.reconciliation_service import ReconciliationService


class _StubExecutionAdapter:
    def __init__(
        self,
        *,
        deployment_states: dict[str, dict[str, float | str | None]],
        order_states: dict[str, OrderRecord],
    ) -> None:
        self._deployment_states = deployment_states
        self._order_states = order_states

    async def get_deployment(
        self,
        *,
        provider_deployment_id: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, float | str | None]:
        return deepcopy(self._deployment_states.get(provider_deployment_id, {"status": "failed", "latestPnl": None}))

    async def get_order(self, *, provider_order_id: str, tenant_id: str, user_id: str) -> OrderRecord | None:
        order = self._order_states.get(provider_order_id)
        return deepcopy(order) if order is not None else None


async def _run_reconciliation_flow() -> None:
    store = InMemoryStateStore()
    store.deployments = {
        "dep-001": DeploymentRecord(
            id="dep-001",
            strategy_id="strat-001",
            mode="paper",
            status="running",
            capital=10000,
            provider_ref_id="provider-dep-001",
        )
    }
    store.orders = {
        "ord-001": OrderRecord(
            id="ord-001",
            symbol="BTCUSDT",
            side="buy",
            order_type="market",
            quantity=0.25,
            price=None,
            status="pending",
            deployment_id="dep-001",
            provider_order_id="provider-ord-001",
        )
    }

    adapter = _StubExecutionAdapter(
        deployment_states={"provider-dep-001": {"status": "stopped", "latestPnl": 42.0}},
        order_states={
            "provider-ord-001": OrderRecord(
                id="ord-001",
                symbol="BTCUSDT",
                side="buy",
                order_type="market",
                quantity=0.25,
                price=None,
                status="filled",
                deployment_id="dep-001",
                provider_order_id="provider-ord-001",
            )
        },
    )
    service = ReconciliationService(store=store, execution_adapter=adapter)

    summary = await service.run_drift_checks(tenant_id="tenant-a", user_id="user-a")
    assert summary.deployment_checks >= 1
    assert summary.drift_count >= 2
    assert len(store.drift_events) >= 2
    sample_event = next(iter(store.drift_events.values()))
    assert sample_event.metadata["tenantId"] == "tenant-a"
    assert sample_event.metadata["userId"] == "user-a"


def test_reconciliation_detects_and_records_drift() -> None:
    asyncio.run(_run_reconciliation_flow())
