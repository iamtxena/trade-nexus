"""Contract tests for AG-RISK-02 pre-trade risk gates."""

from __future__ import annotations

import asyncio

from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import CreateDeploymentRequest, CreateOrderRequest, RequestContext
from src.platform_api.services.execution_service import ExecutionService
from src.platform_api.state_store import InMemoryStateStore


class _StubExecutionAdapter:
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
            "providerDeploymentId": "live-dep-risk-001",
            "deploymentId": "dep-risk-001",
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
            "providerOrderId": "live-order-risk-001",
            "orderId": "ord-risk-001",
            "status": "pending",
        }


def _context() -> RequestContext:
    return RequestContext(
        request_id="req-risk-pretrade-001",
        tenant_id="tenant-a",
        user_id="user-a",
    )


async def _create_service_and_store() -> tuple[ExecutionService, InMemoryStateStore, _StubExecutionAdapter]:
    store = InMemoryStateStore()
    adapter = _StubExecutionAdapter()
    service = ExecutionService(
        store=store,
        execution_adapter=adapter,
    )
    return service, store, adapter


def test_pretrade_blocks_deployment_before_side_effect_when_notional_breached() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["limits"]["maxNotionalUsd"] = 10_000
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 5_000

        try:
            await service.create_deployment(
                request=CreateDeploymentRequest(strategyId="strat-001", mode="paper", capital=20_000),
                idempotency_key="idem-risk-dep-001",
                context=_context(),
            )
            raise AssertionError("Expected pre-trade risk check to block deployment.")
        except PlatformAPIError as exc:
            assert exc.status_code == 422
            assert exc.code == "RISK_LIMIT_BREACH"
        assert adapter.create_deployment_calls == 0

    asyncio.run(_run())


def test_pretrade_blocks_order_when_kill_switch_is_active() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["killSwitch"] = {
            "enabled": True,
            "triggered": True,
            "triggeredAt": "2026-02-15T00:00:00Z",
            "reason": "drawdown breached",
        }

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
                idempotency_key="idem-risk-order-001",
                context=_context(),
            )
            raise AssertionError("Expected kill-switch to block order side effect.")
        except PlatformAPIError as exc:
            assert exc.status_code == 423
            assert exc.code == "RISK_KILL_SWITCH_ACTIVE"
        assert adapter.place_order_calls == 0

    asyncio.run(_run())


def test_pretrade_fails_closed_when_risk_policy_is_invalid() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["version"] = "risk-policy.v2"

        try:
            await service.create_order(
                request=CreateOrderRequest(
                    symbol="BTCUSDT",
                    side="buy",
                    type="limit",
                    quantity=0.05,
                    price=63000,
                    deploymentId="dep-001",
                ),
                idempotency_key="idem-risk-order-002",
                context=_context(),
            )
            raise AssertionError("Expected invalid policy to fail closed.")
        except PlatformAPIError as exc:
            assert exc.status_code == 500
            assert exc.code == "RISK_POLICY_INVALID"
        assert adapter.place_order_calls == 0

    asyncio.run(_run())


def test_pretrade_allows_side_effect_when_policy_passes() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["limits"]["maxNotionalUsd"] = 2_000_000
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 500_000

        response = await service.create_order(
            request=CreateOrderRequest(
                symbol="BTCUSDT",
                side="buy",
                type="limit",
                quantity=0.1,
                price=50000,
                deploymentId="dep-001",
            ),
            idempotency_key="idem-risk-order-003",
            context=_context(),
        )

        assert response.order.id == "ord-risk-001"
        assert adapter.place_order_calls == 1

    asyncio.run(_run())


def test_pretrade_advisory_mode_does_not_block_side_effects() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["mode"] = "advisory"
        store.risk_policy["killSwitch"] = {
            "enabled": True,
            "triggered": True,
            "triggeredAt": "2026-02-15T00:00:00Z",
            "reason": "advisory mode should not hard-block",
        }
        store.risk_policy["limits"]["maxNotionalUsd"] = 1
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 1

        response = await service.create_order(
            request=CreateOrderRequest(
                symbol="BTCUSDT",
                side="buy",
                type="limit",
                quantity=1,
                price=100_000,
                deploymentId="dep-001",
            ),
            idempotency_key="idem-risk-order-004",
            context=_context(),
        )

        assert response.order.id == "ord-risk-001"
        assert adapter.place_order_calls == 1

    asyncio.run(_run())


def test_pretrade_blocks_market_order_without_reference_price() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.portfolios = {}

        try:
            await service.create_order(
                request=CreateOrderRequest(
                    symbol="ETHUSDT",
                    side="buy",
                    type="market",
                    quantity=0.5,
                    deploymentId="dep-001",
                ),
                idempotency_key="idem-risk-order-005",
                context=_context(),
            )
            raise AssertionError("Expected market order without reference price to be blocked.")
        except PlatformAPIError as exc:
            assert exc.status_code == 422
            assert exc.code == "RISK_REFERENCE_PRICE_REQUIRED"
        assert adapter.place_order_calls == 0

    asyncio.run(_run())
