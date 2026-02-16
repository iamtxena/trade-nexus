"""Contract tests for AG-RISK-04 risk decision audit persistence."""

from __future__ import annotations

import asyncio

from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import CreateOrderRequest, RequestContext
from src.platform_api.services.execution_service import ExecutionService
from src.platform_api.state_store import InMemoryStateStore, RiskAuditRecord


class _StubExecutionAdapter:
    def __init__(self, *, latest_pnl: float = -100.0) -> None:
        self.latest_pnl = latest_pnl
        self.place_order_calls = 0
        self.stop_calls = 0

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
            "providerOrderId": "live-order-risk-audit-001",
            "orderId": "ord-risk-audit-001",
            "status": "pending",
        }

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


def _context() -> RequestContext:
    return RequestContext(
        request_id="req-risk-audit-001",
        tenant_id="tenant-a",
        user_id="user-a",
    )


def _latest_audit_record(store: InMemoryStateStore) -> RiskAuditRecord:
    assert store.risk_audit_trail
    return list(store.risk_audit_trail.values())[-1]


def test_risk_audit_records_blocked_pretrade_decision() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        store.risk_policy["killSwitch"] = {"enabled": True, "triggered": True}
        store.volatility_forecasts["BTCUSDT"] = {"predictedPct": 120.0, "confidence": 0.2}
        adapter = _StubExecutionAdapter()
        service = ExecutionService(store=store, execution_adapter=adapter)

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
                idempotency_key="idem-risk-audit-001",
                context=_context(),
            )
            raise AssertionError("Expected risk gate to block order.")
        except PlatformAPIError as exc:
            assert exc.code == "RISK_KILL_SWITCH_ACTIVE"

        record = _latest_audit_record(store)
        assert record.decision == "blocked"
        assert record.check_type == "pretrade_order"
        assert record.outcome_code == "RISK_KILL_SWITCH_ACTIVE"
        assert record.request_id == "req-risk-audit-001"
        assert record.metadata["volatilityForecastPct"] == 120.0
        assert record.metadata["volatilityForecastConfidence"] == 0.2
        assert record.metadata["volatilitySizingMultiplier"] == 1.0
        assert record.metadata["volatilityFallbackUsed"] is True
        assert record.metadata["volatilityFallbackReason"] == "volatility_confidence_low"
        assert adapter.place_order_calls == 0

    asyncio.run(_run())


def test_risk_audit_records_approved_pretrade_decision() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        store.risk_policy["limits"]["maxNotionalUsd"] = 2_000_000
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 500_000
        adapter = _StubExecutionAdapter()
        service = ExecutionService(store=store, execution_adapter=adapter)

        await service.create_order(
            request=CreateOrderRequest(
                symbol="BTCUSDT",
                side="buy",
                type="limit",
                quantity=0.05,
                price=64000,
                deploymentId="dep-001",
            ),
            idempotency_key="idem-risk-audit-002",
            context=_context(),
        )

        record = _latest_audit_record(store)
        assert record.decision == "approved"
        assert record.check_type == "pretrade_order"
        assert record.outcome_code is None
        assert record.metadata["volatilityForecastPct"] == 50.0
        assert record.metadata["volatilityForecastConfidence"] == 0.0
        assert record.metadata["volatilitySizingMultiplier"] == 1.0
        assert record.metadata["volatilityFallbackUsed"] is True
        assert record.metadata["volatilityFallbackReason"] == "volatility_forecast_missing"
        assert adapter.place_order_calls == 1

    asyncio.run(_run())


def test_risk_audit_records_runtime_drawdown_breach() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        store.risk_policy["limits"]["maxDrawdownPct"] = 5.0
        adapter = _StubExecutionAdapter(latest_pnl=-1000.0)
        service = ExecutionService(store=store, execution_adapter=adapter)

        response = await service.get_deployment(deployment_id="dep-001", context=_context())
        assert response.deployment.status == "stopping"

        record = _latest_audit_record(store)
        assert record.decision == "blocked"
        assert record.check_type == "runtime_drawdown"
        assert record.outcome_code == "RISK_DRAWDOWN_BREACH"
        assert record.resource_id == "dep-001"
        assert adapter.stop_calls == 1

    asyncio.run(_run())


def test_risk_audit_records_policy_validation_fail_closed() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        store.risk_policy["version"] = "risk-policy.v2"
        adapter = _StubExecutionAdapter()
        service = ExecutionService(store=store, execution_adapter=adapter)

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
                idempotency_key="idem-risk-audit-003",
                context=_context(),
            )
            raise AssertionError("Expected invalid risk policy to fail closed.")
        except PlatformAPIError as exc:
            assert exc.code == "RISK_POLICY_INVALID"

        record = _latest_audit_record(store)
        assert record.decision == "blocked"
        assert record.check_type == "pretrade_order"
        assert record.outcome_code == "RISK_POLICY_INVALID"
        assert adapter.place_order_calls == 0

    asyncio.run(_run())
