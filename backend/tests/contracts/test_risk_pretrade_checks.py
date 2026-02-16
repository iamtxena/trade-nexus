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


def test_pretrade_sell_order_reduces_projected_notional() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        # Existing seeded portfolio carries notional around 19k; sell should reduce exposure.
        store.risk_policy["limits"]["maxNotionalUsd"] = 20_000
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 20_000

        response = await service.create_order(
            request=CreateOrderRequest(
                symbol="BTCUSDT",
                side="sell",
                type="limit",
                quantity=0.1,
                price=50_000,
                deploymentId="dep-001",
            ),
            idempotency_key="idem-risk-order-006",
            context=_context(),
        )
        assert response.order.side == "sell"
        assert adapter.place_order_calls == 1

    asyncio.run(_run())


def test_pretrade_blocks_buy_when_projected_symbol_position_exceeds_limit() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 20_000
        store.risk_policy["limits"]["maxNotionalUsd"] = 1_000_000

        # Seeded BTC position is about 19,440 notional; buy of 1,000 should breach 20,000 cap.
        try:
            await service.create_order(
                request=CreateOrderRequest(
                    symbol="BTCUSDT",
                    side="buy",
                    type="limit",
                    quantity=0.02,
                    price=50_000,
                    deploymentId="dep-001",
                ),
                idempotency_key="idem-risk-order-007",
                context=_context(),
            )
            raise AssertionError("Expected projected symbol position breach to block order.")
        except PlatformAPIError as exc:
            assert exc.status_code == 422
            assert exc.code == "RISK_LIMIT_BREACH"
        assert adapter.place_order_calls == 0

    asyncio.run(_run())


def test_pretrade_blocks_deployment_when_volatility_adjusted_limit_is_breached() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["limits"]["maxNotionalUsd"] = 100_000
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 100_000
        store.volatility_forecasts["__market__"] = {"predictedPct": 80.0, "confidence": 0.9}

        try:
            await service.create_deployment(
                request=CreateDeploymentRequest(strategyId="strat-001", mode="paper", capital=60_000),
                idempotency_key="idem-risk-dep-ml-001",
                context=_context(),
            )
            raise AssertionError("Expected volatility-adjusted deployment sizing to block.")
        except PlatformAPIError as exc:
            assert exc.status_code == 422
            assert exc.code == "RISK_LIMIT_BREACH"
            assert "volatility-adjusted risk maxNotionalUsd" in exc.message
        assert adapter.create_deployment_calls == 0

    asyncio.run(_run())


def test_pretrade_blocks_order_when_volatility_adjusted_limit_is_breached() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["limits"]["maxNotionalUsd"] = 100_000
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 100_000
        store.volatility_forecasts["BTCUSDT"] = {"predictedPct": 95.0, "confidence": 0.9}

        try:
            await service.create_order(
                request=CreateOrderRequest(
                    symbol="BTCUSDT",
                    side="buy",
                    type="limit",
                    quantity=1.0,
                    price=50_000,
                    deploymentId="dep-001",
                ),
                idempotency_key="idem-risk-order-ml-001",
                context=_context(),
            )
            raise AssertionError("Expected volatility-adjusted order sizing to block.")
        except PlatformAPIError as exc:
            assert exc.status_code == 422
            assert exc.code == "RISK_LIMIT_BREACH"
            assert "volatility-adjusted risk maxPositionNotionalUsd" in exc.message
        assert adapter.place_order_calls == 0

    asyncio.run(_run())


def test_pretrade_uses_market_forecast_when_symbol_forecast_is_malformed() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["limits"]["maxNotionalUsd"] = 100_000
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 100_000
        store.volatility_forecasts["BTCUSDT"] = {"predictedPct": "invalid", "confidence": 0.9}
        store.volatility_forecasts["__market__"] = {"predictedPct": 95.0, "confidence": 0.9}

        try:
            await service.create_order(
                request=CreateOrderRequest(
                    symbol="BTCUSDT",
                    side="buy",
                    type="limit",
                    quantity=1.0,
                    price=50_000,
                    deploymentId="dep-001",
                ),
                idempotency_key="idem-risk-order-ml-003",
                context=_context(),
            )
            raise AssertionError("Expected market-level volatility sizing to block malformed symbol forecast.")
        except PlatformAPIError as exc:
            assert exc.status_code == 422
            assert exc.code == "RISK_LIMIT_BREACH"
            assert "volatility-adjusted risk maxPositionNotionalUsd" in exc.message

        assert adapter.place_order_calls == 0
        assert store.risk_audit_trail
        metadata = list(store.risk_audit_trail.values())[-1].metadata
        assert metadata["volatilityForecastSource"] == "__market__"
        assert metadata["volatilitySizingMultiplier"] == 0.35
        assert metadata["volatilityFallbackUsed"] is False

    asyncio.run(_run())


def test_pretrade_uses_deterministic_fallback_when_volatility_confidence_is_low() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["limits"]["maxNotionalUsd"] = 60_000
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 60_000
        store.volatility_forecasts["BTCUSDT"] = {"predictedPct": 95.0, "confidence": 0.2}

        response = await service.create_order(
            request=CreateOrderRequest(
                symbol="BTCUSDT",
                side="buy",
                type="limit",
                quantity=0.6,
                price=50_000,
                deploymentId="dep-001",
            ),
            idempotency_key="idem-risk-order-ml-002",
            context=_context(),
        )

        assert response.order.id == "ord-risk-001"
        assert adapter.place_order_calls == 1

    asyncio.run(_run())


def test_pretrade_uses_deterministic_fallback_when_volatility_confidence_is_nan() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["limits"]["maxNotionalUsd"] = 60_000
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 60_000
        store.volatility_forecasts["BTCUSDT"] = {"predictedPct": 95.0, "confidence": float("nan")}

        response = await service.create_order(
            request=CreateOrderRequest(
                symbol="BTCUSDT",
                side="buy",
                type="limit",
                quantity=0.6,
                price=50_000,
                deploymentId="dep-001",
            ),
            idempotency_key="idem-risk-order-ml-004",
            context=_context(),
        )

        assert response.order.id == "ord-risk-001"
        assert adapter.place_order_calls == 1
        assert store.risk_audit_trail
        metadata = list(store.risk_audit_trail.values())[-1].metadata
        assert metadata["volatilityForecastPct"] == 50.0
        assert metadata["volatilityForecastConfidence"] == 0.0
        assert metadata["volatilitySizingMultiplier"] == 1.0
        assert metadata["volatilityFallbackUsed"] is True
        assert metadata["volatilityFallbackReason"] == "volatility_confidence_invalid"

    asyncio.run(_run())


def test_pretrade_blocks_order_when_ml_anomaly_breach_is_active() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["limits"]["maxNotionalUsd"] = 2_000_000
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 500_000
        store.ml_signal_snapshots["__market__"] = {
            "regime": "risk_off",
            "regimeConfidence": 0.86,
            "anomalyScore": 0.92,
            "anomalyConfidence": 0.9,
            "anomalyFlag": True,
        }

        try:
            await service.create_order(
                request=CreateOrderRequest(
                    symbol="BTCUSDT",
                    side="buy",
                    type="limit",
                    quantity=0.1,
                    price=50_000,
                    deploymentId="dep-001",
                ),
                idempotency_key="idem-risk-order-ml-005",
                context=_context(),
            )
            raise AssertionError("Expected anomaly breach to block order.")
        except PlatformAPIError as exc:
            assert exc.status_code == 423
            assert exc.code == "RISK_ML_ANOMALY_BREACH"

        assert adapter.place_order_calls == 0
        assert store.risk_audit_trail
        metadata = list(store.risk_audit_trail.values())[-1].metadata
        assert metadata["mlAnomalyBreach"] is True
        assert metadata["mlSignalFallbackUsed"] is False

    asyncio.run(_run())


def test_pretrade_applies_risk_off_regime_multiplier_to_limits() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["limits"]["maxNotionalUsd"] = 100_000
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 100_000
        store.ml_signal_snapshots["__market__"] = {
            "regime": "risk_off",
            "regimeConfidence": 0.84,
            "anomalyScore": 0.2,
            "anomalyConfidence": 0.8,
            "anomalyFlag": False,
        }

        try:
            await service.create_deployment(
                request=CreateDeploymentRequest(strategyId="strat-001", mode="paper", capital=80_000),
                idempotency_key="idem-risk-dep-ml-006",
                context=_context(),
            )
            raise AssertionError("Expected regime-adjusted limit to block deployment.")
        except PlatformAPIError as exc:
            assert exc.status_code == 422
            assert exc.code == "RISK_LIMIT_BREACH"

        assert adapter.create_deployment_calls == 0
        assert store.risk_audit_trail
        metadata = list(store.risk_audit_trail.values())[-1].metadata
        assert metadata["mlRegime"] == "risk_off"
        assert metadata["mlRegimeSizingMultiplier"] == 0.7

    asyncio.run(_run())


def test_pretrade_uses_fallback_when_ml_regime_confidence_is_low() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.risk_policy["limits"]["maxNotionalUsd"] = 120_000
        store.risk_policy["limits"]["maxPositionNotionalUsd"] = 120_000
        store.ml_signal_snapshots["__market__"] = {
            "regime": "risk_off",
            "regimeConfidence": 0.2,
            "anomalyScore": 0.2,
            "anomalyConfidence": 0.8,
            "anomalyFlag": False,
        }

        response = await service.create_order(
            request=CreateOrderRequest(
                symbol="BTCUSDT",
                side="buy",
                type="limit",
                quantity=0.1,
                price=50_000,
                deploymentId="dep-001",
            ),
            idempotency_key="idem-risk-order-ml-006",
            context=_context(),
        )

        assert response.order.id == "ord-risk-001"
        assert adapter.place_order_calls == 1
        assert store.risk_audit_trail
        metadata = list(store.risk_audit_trail.values())[-1].metadata
        assert metadata["mlRegime"] == "neutral"
        assert metadata["mlRegimeSizingMultiplier"] == 1.0
        assert metadata["mlSignalFallbackUsed"] is True
        assert "regime_confidence_low" in str(metadata["mlSignalFallbackReason"])

    asyncio.run(_run())
