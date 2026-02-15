"""Contract tests for AG-EXE-03 execution command idempotency."""

from __future__ import annotations

import asyncio

from src.platform_api.errors import PlatformAPIError
from src.platform_api.services.execution_command_service import (
    CreateDeploymentCommand,
    ExecutionCommandService,
    PlaceOrderCommand,
)
from src.platform_api.state_store import InMemoryStateStore


class _CountingAdapter:
    def __init__(self) -> None:
        self.create_deployment_calls = 0
        self.place_order_calls = 0

    async def create_deployment(  # type: ignore[no-untyped-def]
        self,
        *,
        strategy_id: str,
        mode: str,
        capital: float,
        tenant_id: str,
        user_id: str,
        idempotency_key: str,
    ):
        _ = (strategy_id, mode, capital, tenant_id, user_id, idempotency_key)
        self.create_deployment_calls += 1
        return {
            "providerDeploymentId": "live-dep-idem-001",
            "deploymentId": "dep-idem-001",
            "status": "queued",
        }

    async def place_order(  # type: ignore[no-untyped-def]
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None,
        deployment_id: str | None,
        tenant_id: str,
        user_id: str,
        idempotency_key: str,
    ):
        _ = (symbol, side, order_type, quantity, price, deployment_id, tenant_id, user_id, idempotency_key)
        self.place_order_calls += 1
        return {
            "providerOrderId": "live-order-idem-001",
            "orderId": "ord-idem-001",
            "status": "pending",
        }

    async def stop_deployment(self, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return {"status": "stopping"}

    async def cancel_order(self, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        return {"status": "cancelled"}


def test_command_layer_replays_cached_deployment_response() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        adapter = _CountingAdapter()
        service = ExecutionCommandService(execution_adapter=adapter, store=store)  # type: ignore[arg-type]

        command = CreateDeploymentCommand(
            strategy_id="strat-001",
            mode="paper",
            capital=20_000,
            tenant_id="tenant-a",
            user_id="user-a",
            idempotency_key="idem-cmd-deployment-001",
            request_id="req-cmd-idem-001",
        )
        first = await service.create_deployment(command=command)
        second = await service.create_deployment(command=command)

        assert first["deploymentId"] == "dep-idem-001"
        assert second["deploymentId"] == "dep-idem-001"
        assert adapter.create_deployment_calls == 1

    asyncio.run(_run())


def test_command_layer_replays_cached_order_response() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        adapter = _CountingAdapter()
        service = ExecutionCommandService(execution_adapter=adapter, store=store)  # type: ignore[arg-type]

        command = PlaceOrderCommand(
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            quantity=0.1,
            price=64000,
            deployment_id="dep-001",
            tenant_id="tenant-a",
            user_id="user-a",
            idempotency_key="idem-cmd-order-001",
            request_id="req-cmd-idem-002",
        )
        first = await service.place_order(command=command)
        second = await service.place_order(command=command)

        assert first["orderId"] == "ord-idem-001"
        assert second["orderId"] == "ord-idem-001"
        assert adapter.place_order_calls == 1

    asyncio.run(_run())


def test_command_layer_rejects_key_reuse_with_different_payload() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        adapter = _CountingAdapter()
        service = ExecutionCommandService(execution_adapter=adapter, store=store)  # type: ignore[arg-type]

        first = CreateDeploymentCommand(
            strategy_id="strat-001",
            mode="paper",
            capital=20_000,
            tenant_id="tenant-a",
            user_id="user-a",
            idempotency_key="idem-cmd-deployment-002",
            request_id="req-cmd-idem-003",
        )
        await service.create_deployment(command=first)

        conflicting = CreateDeploymentCommand(
            strategy_id="strat-001",
            mode="paper",
            capital=21_000,
            tenant_id="tenant-a",
            user_id="user-a",
            idempotency_key="idem-cmd-deployment-002",
            request_id="req-cmd-idem-003",
        )
        try:
            await service.create_deployment(command=conflicting)
            raise AssertionError("Expected idempotency conflict for changed command payload.")
        except PlatformAPIError as exc:
            assert exc.status_code == 409
            assert exc.code == "IDEMPOTENCY_KEY_CONFLICT"

        assert adapter.create_deployment_calls == 1

    asyncio.run(_run())
