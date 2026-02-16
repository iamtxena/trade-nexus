"""Contract tests for AG-EXE-01 execution command layer boundary."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from src.platform_api.schemas_v1 import CreateDeploymentRequest, CreateOrderRequest, RequestContext
from src.platform_api.services.execution_service import ExecutionService
from src.platform_api.state_store import InMemoryStateStore, OrderRecord


class _NoSideEffectAdapter:
    """Adapter double that raises if side-effecting methods are called directly."""

    def __init__(self, *, latest_pnl: float = 0.0) -> None:
        self.latest_pnl = latest_pnl

    async def create_deployment(self, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        raise AssertionError("create_deployment must be invoked via execution command layer.")

    async def stop_deployment(self, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        raise AssertionError("stop_deployment must be invoked via execution command layer.")

    async def place_order(self, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        raise AssertionError("place_order must be invoked via execution command layer.")

    async def cancel_order(self, **kwargs):  # type: ignore[no-untyped-def]
        _ = kwargs
        raise AssertionError("cancel_order must be invoked via execution command layer.")

    async def get_deployment(  # type: ignore[no-untyped-def]
        self,
        *,
        provider_deployment_id: str,
        tenant_id: str,
        user_id: str,
    ):
        _ = (provider_deployment_id, tenant_id, user_id)
        return {"status": "running", "latestPnl": self.latest_pnl}

    async def list_deployments(  # type: ignore[no-untyped-def]
        self,
        *,
        status: str | None,
        tenant_id: str,
        user_id: str,
    ):
        _ = (status, tenant_id, user_id)
        return []

    async def list_orders(  # type: ignore[no-untyped-def]
        self,
        *,
        status: str | None,
        tenant_id: str,
        user_id: str,
    ):
        _ = (status, tenant_id, user_id)
        return []

    async def get_order(self, *, provider_order_id: str, tenant_id: str, user_id: str):  # type: ignore[no-untyped-def]
        _ = (provider_order_id, tenant_id, user_id)
        return None

    async def get_portfolio_snapshot(  # type: ignore[no-untyped-def]
        self,
        *,
        portfolio_id: str,
        tenant_id: str,
        user_id: str,
    ):
        _ = (portfolio_id, tenant_id, user_id)
        return None

    async def list_portfolios(self, *, tenant_id: str, user_id: str):  # type: ignore[no-untyped-def]
        _ = (tenant_id, user_id)
        return []


@dataclass
class _StubExecutionCommandService:
    create_deployment_calls: int = 0
    stop_deployment_calls: int = 0
    place_order_calls: int = 0
    cancel_order_calls: int = 0
    received_commands: list[Any] = field(default_factory=list)

    async def create_deployment(self, *, command):  # type: ignore[no-untyped-def]
        self.create_deployment_calls += 1
        self.received_commands.append(command)
        return {
            "providerDeploymentId": "live-dep-cmd-001",
            "deploymentId": "dep-cmd-001",
            "status": "queued",
        }

    async def stop_deployment(self, *, command):  # type: ignore[no-untyped-def]
        self.stop_deployment_calls += 1
        self.received_commands.append(command)
        return {"status": "stopping"}

    async def place_order(self, *, command):  # type: ignore[no-untyped-def]
        self.place_order_calls += 1
        self.received_commands.append(command)
        return {
            "providerOrderId": "live-order-cmd-001",
            "orderId": "ord-cmd-001",
            "status": "pending",
        }

    async def cancel_order(self, *, command):  # type: ignore[no-untyped-def]
        self.cancel_order_calls += 1
        self.received_commands.append(command)
        return {"status": "cancelled"}


def _context() -> RequestContext:
    return RequestContext(
        request_id="req-exe-command-001",
        tenant_id="tenant-a",
        user_id="user-a",
    )


def test_execution_side_effects_use_command_layer() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        adapter = _NoSideEffectAdapter()
        command_service = _StubExecutionCommandService()
        service = ExecutionService(
            store=store,
            execution_adapter=adapter,
            execution_command_service=command_service,  # type: ignore[arg-type]
        )

        create_dep_response = await service.create_deployment(
            request=CreateDeploymentRequest(strategyId="strat-001", mode="paper", capital=20_000),
            idempotency_key="idem-cmd-dep-001",
            context=_context(),
        )
        assert create_dep_response.deployment.id == "dep-cmd-001"

        create_order_response = await service.create_order(
            request=CreateOrderRequest(
                symbol="BTCUSDT",
                side="buy",
                type="limit",
                quantity=0.1,
                price=64000,
                deploymentId="dep-001",
            ),
            idempotency_key="idem-cmd-order-001",
            context=_context(),
        )
        assert create_order_response.order.id == "ord-cmd-001"

        stop_response = await service.stop_deployment(
            deployment_id="dep-001",
            reason="manual stop",
            context=_context(),
        )
        assert stop_response.deployment.status == "stopping"

        store.orders["ord-cmd-cancel-001"] = OrderRecord(
            id="ord-cmd-cancel-001",
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            quantity=0.1,
            price=64000,
            status="pending",
            deployment_id="dep-001",
            provider_order_id="live-order-cmd-cancel-001",
        )
        cancel_response = await service.cancel_order(order_id="ord-cmd-cancel-001", context=_context())
        assert cancel_response.order.status == "cancelled"

        assert command_service.create_deployment_calls == 1
        assert command_service.place_order_calls == 1
        assert command_service.stop_deployment_calls == 1
        assert command_service.cancel_order_calls == 1

    asyncio.run(_run())


def test_drawdown_stop_path_uses_command_layer() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        store.risk_policy["limits"]["maxDrawdownPct"] = 5.0
        adapter = _NoSideEffectAdapter(latest_pnl=-2000.0)
        command_service = _StubExecutionCommandService()
        service = ExecutionService(
            store=store,
            execution_adapter=adapter,
            execution_command_service=command_service,  # type: ignore[arg-type]
        )

        response = await service.get_deployment(deployment_id="dep-001", context=_context())
        assert response.deployment.status == "stopping"
        assert command_service.stop_deployment_calls == 1

    asyncio.run(_run())
