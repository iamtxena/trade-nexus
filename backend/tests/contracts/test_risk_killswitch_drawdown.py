"""Contract tests for AG-RISK-03 drawdown breach and kill-switch handling."""

from __future__ import annotations

import asyncio

from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import CreateOrderRequest, RequestContext
from src.platform_api.services.execution_service import ExecutionService
from src.platform_api.state_store import InMemoryStateStore


class _StubExecutionAdapter:
    def __init__(self, *, latest_pnl: float) -> None:
        self.latest_pnl = latest_pnl
        self.stop_calls = 0
        self.place_order_calls = 0

    async def get_deployment(  # type: ignore[no-untyped-def]
        self,
        *,
        provider_deployment_id: str,
        tenant_id: str,
        user_id: str,
    ):
        _ = (provider_deployment_id, tenant_id, user_id)
        return {
            "status": "running",
            "latestPnl": self.latest_pnl,
        }

    async def stop_deployment(  # type: ignore[no-untyped-def]
        self,
        *,
        provider_deployment_id: str,
        reason: str | None,
        tenant_id: str,
        user_id: str,
    ):
        _ = (provider_deployment_id, reason, tenant_id, user_id)
        self.stop_calls += 1
        return {"status": "stopping"}

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
            "providerOrderId": "live-order-risk-ks-001",
            "orderId": "ord-risk-ks-001",
            "status": "pending",
        }


def _context() -> RequestContext:
    return RequestContext(
        request_id="req-risk-killswitch-001",
        tenant_id="tenant-a",
        user_id="user-a",
    )


def test_drawdown_breach_triggers_killswitch_and_stop_flow() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        store.risk_policy["limits"]["maxDrawdownPct"] = 5.0
        adapter = _StubExecutionAdapter(latest_pnl=-1000.0)  # 5% drawdown on 20k capital.
        service = ExecutionService(store=store, execution_adapter=adapter)

        response = await service.get_deployment(deployment_id="dep-001", context=_context())
        assert response.deployment.status == "stopping"
        assert adapter.stop_calls == 1
        assert bool(store.risk_policy["killSwitch"]["triggered"])
        assert "dep-001" in str(store.risk_policy["killSwitch"]["reason"])

    asyncio.run(_run())


def test_non_breach_drawdown_does_not_trigger_killswitch() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        store.risk_policy["limits"]["maxDrawdownPct"] = 5.0
        adapter = _StubExecutionAdapter(latest_pnl=-100.0)  # 0.5% drawdown on 20k capital.
        service = ExecutionService(store=store, execution_adapter=adapter)

        response = await service.get_deployment(deployment_id="dep-001", context=_context())
        assert response.deployment.status == "running"
        assert adapter.stop_calls == 0
        assert not bool(store.risk_policy["killSwitch"]["triggered"])

    asyncio.run(_run())


def test_triggered_killswitch_blocks_followup_order_side_effects() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        store.risk_policy["limits"]["maxDrawdownPct"] = 5.0
        adapter = _StubExecutionAdapter(latest_pnl=-1000.0)
        service = ExecutionService(store=store, execution_adapter=adapter)

        await service.get_deployment(deployment_id="dep-001", context=_context())

        try:
            await service.create_order(
                request=CreateOrderRequest(
                    symbol="BTCUSDT",
                    side="buy",
                    type="limit",
                    quantity=0.1,
                    price=64000,
                    deploymentId="dep-001",
                ),
                idempotency_key="idem-risk-ks-order-001",
                context=_context(),
            )
            raise AssertionError("Expected kill-switch to block follow-up order.")
        except PlatformAPIError as exc:
            assert exc.status_code == 423
            assert exc.code == "RISK_KILL_SWITCH_ACTIVE"
        assert adapter.place_order_calls == 0

    asyncio.run(_run())
