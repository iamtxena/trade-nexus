"""Pre-trade risk gate for execution side-effecting commands (AG-RISK-02)."""

from __future__ import annotations

from dataclasses import dataclass
import math

from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import CreateDeploymentRequest, CreateOrderRequest, RequestContext
from src.platform_api.services.risk_audit_service import RiskAuditService
from src.platform_api.services.ml_signal_constants import (
    ANOMALY_BREACH_CONFIDENCE,
    ANOMALY_BREACH_SCORE,
    ML_SIGNAL_MARKET_KEY,
    REGIME_ALIASES,
    REGIME_CONFIDENCE_MIN,
)
from src.platform_api.services.risk_policy import RiskPolicyValidationError, validate_risk_policy
from src.platform_api.state_store import InMemoryStateStore

_ACTIVE_DEPLOYMENT_STATES = {"queued", "running", "paused"}
_VOLATILITY_FORECAST_MARKET_KEY = "__market__"


@dataclass(frozen=True)
class VolatilitySizingContext:
    predicted_pct: float
    confidence: float
    sizing_multiplier: float
    source: str
    fallback_reason: str | None = None

    @property
    def used_fallback(self) -> bool:
        return self.fallback_reason is not None


@dataclass(frozen=True)
class MLRiskSignalContext:
    regime: str
    regime_confidence: float
    regime_multiplier: float
    anomaly_score: float
    anomaly_confidence: float
    anomaly_flag: bool
    anomaly_breach: bool
    source: str
    fallback_reason: str | None = None

    @property
    def used_fallback(self) -> bool:
        return self.fallback_reason is not None


class RiskPreTradeService:
    """Validates policy and enforces pre-trade limits before execution side effects."""

    def __init__(self, *, store: InMemoryStateStore) -> None:
        self._store = store
        self._risk_audit_service = RiskAuditService(store=store)

    def ensure_deployment_allowed(
        self,
        *,
        request: CreateDeploymentRequest,
        context: RequestContext,
    ) -> None:
        volatility = self._resolve_volatility_sizing(symbol=None)
        volatility_metadata = self._volatility_metadata(volatility)
        ml_context = self._resolve_ml_risk_signals(symbol=None)
        ml_metadata = self._ml_risk_metadata(ml_context)
        try:
            policy = self._validated_policy(context=context)
            self._ensure_ml_anomaly_not_breached(context=context, ml_context=ml_context)
            effective_max_notional = (
                policy.limits.maxNotionalUsd
                * volatility.sizing_multiplier
                * ml_context.regime_multiplier
            )
            if policy.mode == "advisory":
                self._record_allow(
                    check_type="pretrade_deployment",
                    resource_type="deployment",
                    resource_id=request.strategyId,
                    context=context,
                    policy_version=policy.version,
                    policy_mode=policy.mode,
                    metadata={
                        "capital": request.capital,
                        "mode": request.mode,
                        "reason": "advisory_mode",
                        "effectiveMaxNotionalUsd": effective_max_notional,
                        **volatility_metadata,
                        **ml_metadata,
                    },
                )
                return
            self._ensure_kill_switch_not_triggered(context=context)

            active_deployment_capital = sum(
                deployment.capital
                for deployment in self._store.deployments.values()
                if deployment.status in _ACTIVE_DEPLOYMENT_STATES
            )
            projected_total = active_deployment_capital + request.capital

            if request.capital > effective_max_notional:
                raise self._limit_breach(
                    context=context,
                    message=(
                        "Deployment capital exceeds volatility-adjusted risk maxNotionalUsd "
                        f"({request.capital} > {effective_max_notional}; "
                        f"base={policy.limits.maxNotionalUsd}, multiplier={volatility.sizing_multiplier})."
                    ),
                )
            if projected_total > effective_max_notional:
                raise self._limit_breach(
                    context=context,
                    message=(
                        "Projected active deployment capital exceeds volatility-adjusted risk maxNotionalUsd "
                        f"({projected_total} > {effective_max_notional}; "
                        f"base={policy.limits.maxNotionalUsd}, multiplier={volatility.sizing_multiplier})."
                    ),
                )

            self._record_allow(
                check_type="pretrade_deployment",
                resource_type="deployment",
                resource_id=request.strategyId,
                context=context,
                policy_version=policy.version,
                policy_mode=policy.mode,
                metadata={
                    "capital": request.capital,
                    "mode": request.mode,
                    "projectedCapital": projected_total,
                    "effectiveMaxNotionalUsd": effective_max_notional,
                    **volatility_metadata,
                    **ml_metadata,
                },
            )
        except PlatformAPIError as exc:
            self._record_block(
                check_type="pretrade_deployment",
                resource_type="deployment",
                resource_id=request.strategyId,
                context=context,
                outcome_code=exc.code,
                reason=exc.message,
                metadata={
                    "capital": request.capital,
                    "mode": request.mode,
                    **volatility_metadata,
                    **ml_metadata,
                },
            )
            raise

    def ensure_order_allowed(
        self,
        *,
        request: CreateOrderRequest,
        context: RequestContext,
    ) -> None:
        volatility = self._resolve_volatility_sizing(symbol=request.symbol)
        volatility_metadata = self._volatility_metadata(volatility)
        ml_context = self._resolve_ml_risk_signals(symbol=request.symbol)
        ml_metadata = self._ml_risk_metadata(ml_context)
        try:
            policy = self._validated_policy(context=context)
            self._ensure_ml_anomaly_not_breached(context=context, ml_context=ml_context)
            effective_max_notional = (
                policy.limits.maxNotionalUsd
                * volatility.sizing_multiplier
                * ml_context.regime_multiplier
            )
            effective_max_position_notional = (
                policy.limits.maxPositionNotionalUsd
                * volatility.sizing_multiplier
                * ml_context.regime_multiplier
            )
            if policy.mode == "advisory":
                self._record_allow(
                    check_type="pretrade_order",
                    resource_type="order",
                    resource_id=request.deploymentId,
                    context=context,
                    policy_version=policy.version,
                    policy_mode=policy.mode,
                    metadata={
                        "symbol": request.symbol,
                        "side": request.side,
                        "quantity": request.quantity,
                        "reason": "advisory_mode",
                        "effectiveMaxNotionalUsd": effective_max_notional,
                        "effectiveMaxPositionNotionalUsd": effective_max_position_notional,
                        **volatility_metadata,
                        **ml_metadata,
                    },
                )
                return
            self._ensure_kill_switch_not_triggered(context=context)

            reference_price = self._resolve_reference_price(request=request)
            if reference_price is None:
                raise PlatformAPIError(
                    status_code=422,
                    code="RISK_REFERENCE_PRICE_REQUIRED",
                    message=(
                        "Market order risk checks require a reference price; provide a limit price "
                        "or ensure symbol context is available."
                    ),
                    request_id=context.request_id,
                )
            order_notional = request.quantity * reference_price

            existing_symbol_notional = 0.0
            for portfolio in self._store.portfolios.values():
                for position in portfolio.positions:
                    if position.symbol == request.symbol:
                        existing_symbol_notional += abs(position.quantity * position.current_price)

            if request.side == "sell":
                projected_symbol_notional = max(0.0, existing_symbol_notional - order_notional)
            else:
                projected_symbol_notional = existing_symbol_notional + order_notional

            if projected_symbol_notional > effective_max_position_notional:
                raise self._limit_breach(
                    context=context,
                    message=(
                        "Projected symbol notional exceeds volatility-adjusted risk maxPositionNotionalUsd "
                        f"({projected_symbol_notional} > {effective_max_position_notional}; "
                        f"base={policy.limits.maxPositionNotionalUsd}, multiplier={volatility.sizing_multiplier})."
                    ),
                )

            if order_notional > effective_max_notional:
                raise self._limit_breach(
                    context=context,
                    message=(
                        "Order notional exceeds volatility-adjusted risk maxNotionalUsd "
                        f"({order_notional} > {effective_max_notional}; "
                        f"base={policy.limits.maxNotionalUsd}, multiplier={volatility.sizing_multiplier})."
                    ),
                )

            estimated_portfolio_notional = 0.0
            for portfolio in self._store.portfolios.values():
                for position in portfolio.positions:
                    estimated_portfolio_notional += abs(position.quantity * position.current_price)

            if request.side == "sell":
                projected_notional = max(0.0, estimated_portfolio_notional - order_notional)
            else:
                projected_notional = estimated_portfolio_notional + order_notional
            if projected_notional > effective_max_notional:
                raise self._limit_breach(
                    context=context,
                    message=(
                        "Projected total notional exceeds volatility-adjusted risk maxNotionalUsd "
                        f"({projected_notional} > {effective_max_notional}; "
                        f"base={policy.limits.maxNotionalUsd}, multiplier={volatility.sizing_multiplier})."
                    ),
                )

            current_daily_loss = 0.0
            for portfolio in self._store.portfolios.values():
                if portfolio.pnl_total is not None and portfolio.pnl_total < 0:
                    current_daily_loss += abs(portfolio.pnl_total)
            if current_daily_loss >= policy.limits.maxDailyLossUsd:
                raise self._limit_breach(
                    context=context,
                    message=(
                        "Daily loss limit reached; new orders are blocked "
                        f"({current_daily_loss} >= {policy.limits.maxDailyLossUsd})."
                    ),
                )

            self._record_allow(
                check_type="pretrade_order",
                resource_type="order",
                resource_id=request.deploymentId,
                context=context,
                policy_version=policy.version,
                policy_mode=policy.mode,
                metadata={
                    "symbol": request.symbol,
                    "side": request.side,
                    "quantity": request.quantity,
                    "referencePrice": reference_price,
                    "orderNotional": order_notional,
                    "projectedSymbolNotional": projected_symbol_notional,
                    "projectedTotalNotional": projected_notional,
                    "effectiveMaxNotionalUsd": effective_max_notional,
                    "effectiveMaxPositionNotionalUsd": effective_max_position_notional,
                    **volatility_metadata,
                    **ml_metadata,
                },
            )
        except PlatformAPIError as exc:
            self._record_block(
                check_type="pretrade_order",
                resource_type="order",
                resource_id=request.deploymentId,
                context=context,
                outcome_code=exc.code,
                reason=exc.message,
                metadata={
                    "symbol": request.symbol,
                    "side": request.side,
                    "quantity": request.quantity,
                    "price": request.price,
                    **volatility_metadata,
                    **ml_metadata,
                },
            )
            raise

    def _validated_policy(self, *, context: RequestContext):
        try:
            return validate_risk_policy(self._store.risk_policy)
        except RiskPolicyValidationError as exc:
            raise PlatformAPIError(
                status_code=500,
                code="RISK_POLICY_INVALID",
                message=f"Risk policy validation failed: {exc}",
                request_id=context.request_id,
            ) from exc

    def _ensure_kill_switch_not_triggered(self, *, context: RequestContext) -> None:
        kill_switch = self._store.risk_policy.get("killSwitch", {})
        if (
            isinstance(kill_switch, dict)
            and bool(kill_switch.get("enabled"))
            and bool(kill_switch.get("triggered"))
        ):
            raise PlatformAPIError(
                status_code=423,
                code="RISK_KILL_SWITCH_ACTIVE",
                message="Risk kill-switch is active; execution side effects are blocked.",
                request_id=context.request_id,
            )

    @staticmethod
    def _limit_breach(*, context: RequestContext, message: str) -> PlatformAPIError:
        return PlatformAPIError(
            status_code=422,
            code="RISK_LIMIT_BREACH",
            message=message,
            request_id=context.request_id,
        )

    def _resolve_reference_price(self, *, request: CreateOrderRequest) -> float | None:
        if request.price is not None:
            return request.price

        # Market orders do not carry explicit price; approximate using known position price.
        for portfolio in self._store.portfolios.values():
            for position in portfolio.positions:
                if position.symbol == request.symbol:
                    return position.current_price
        return None

    def _resolve_volatility_sizing(self, *, symbol: str | None) -> VolatilitySizingContext:
        forecasts = self._store.volatility_forecasts
        if not isinstance(forecasts, dict):
            return self._volatility_fallback(reason="volatility_forecast_missing")

        candidate_keys: list[str] = []
        if symbol:
            candidate_keys.append(symbol.upper())
            if symbol.upper() != symbol:
                candidate_keys.append(symbol)
        candidate_keys.append(_VOLATILITY_FORECAST_MARKET_KEY)

        payload_seen = False
        fallback_reason = "volatility_forecast_missing"
        for key in candidate_keys:
            candidate = forecasts.get(key)
            if not isinstance(candidate, dict):
                continue
            payload_seen = True
            source = key

            raw_predicted_pct = candidate.get("predictedPct")
            raw_confidence = candidate.get("confidence")
            if not isinstance(raw_predicted_pct, (int, float)):
                fallback_reason = "volatility_predicted_pct_missing"
                continue
            if not isinstance(raw_confidence, (int, float)):
                fallback_reason = "volatility_confidence_missing"
                continue

            predicted_pct = float(raw_predicted_pct)
            if not math.isfinite(predicted_pct):
                fallback_reason = "volatility_predicted_pct_invalid"
                continue
            if predicted_pct < 0.0:
                fallback_reason = "volatility_predicted_pct_negative"
                continue
            predicted_pct = self._clamp(predicted_pct, minimum=0.0, maximum=500.0)

            confidence = float(raw_confidence)
            if not math.isfinite(confidence):
                fallback_reason = "volatility_confidence_invalid"
                continue
            if confidence > 1.0:
                confidence = confidence / 100.0
            if confidence < 0.0 or confidence > 1.0:
                fallback_reason = "volatility_confidence_out_of_range"
                continue

            if confidence < 0.55:
                return VolatilitySizingContext(
                    predicted_pct=predicted_pct,
                    confidence=confidence,
                    sizing_multiplier=1.0,
                    source=source,
                    fallback_reason="volatility_confidence_low",
                )

            return VolatilitySizingContext(
                predicted_pct=predicted_pct,
                confidence=confidence,
                sizing_multiplier=self._volatility_multiplier(predicted_pct=predicted_pct),
                source=source,
                fallback_reason=None,
            )

        if payload_seen:
            return self._volatility_fallback(reason=fallback_reason)
        return self._volatility_fallback(reason="volatility_forecast_missing")

    @staticmethod
    def _volatility_multiplier(*, predicted_pct: float) -> float:
        if predicted_pct >= 90.0:
            return 0.35
        if predicted_pct >= 70.0:
            return 0.5
        if predicted_pct >= 55.0:
            return 0.7
        if predicted_pct >= 40.0:
            return 0.85
        return 1.0

    @staticmethod
    def _volatility_metadata(volatility: VolatilitySizingContext) -> dict[str, object]:
        return {
            "volatilityForecastPct": volatility.predicted_pct,
            "volatilityForecastConfidence": volatility.confidence,
            "volatilitySizingMultiplier": volatility.sizing_multiplier,
            "volatilityForecastSource": volatility.source,
            "volatilityFallbackReason": volatility.fallback_reason,
            "volatilityFallbackUsed": volatility.used_fallback,
        }

    @staticmethod
    def _volatility_fallback(*, reason: str) -> VolatilitySizingContext:
        return VolatilitySizingContext(
            predicted_pct=50.0,
            confidence=0.0,
            sizing_multiplier=1.0,
            source="fallback",
            fallback_reason=reason,
        )

    def _resolve_ml_risk_signals(self, *, symbol: str | None) -> MLRiskSignalContext:
        snapshots = self._store.ml_signal_snapshots
        if not isinstance(snapshots, dict):
            return self._ml_risk_fallback(reason="ml_signal_snapshot_missing")

        candidate_keys: list[str] = []
        if symbol:
            upper = symbol.upper()
            candidate_keys.append(upper)
            if upper != symbol:
                candidate_keys.append(symbol)
        candidate_keys.append(ML_SIGNAL_MARKET_KEY)

        for key in candidate_keys:
            payload = snapshots.get(key)
            if not isinstance(payload, dict):
                continue
            return self._ml_risk_from_payload(payload=payload, source=key)

        return self._ml_risk_fallback(reason="ml_signal_snapshot_missing")

    def _ml_risk_from_payload(self, *, payload: dict[str, object], source: str) -> MLRiskSignalContext:
        fallback_reasons: list[str] = []
        regime = self._normalize_regime_label(payload.get("regime"), fallback_reasons)
        regime_confidence = self._coerce_confidence(payload.get("regimeConfidence"), fallback_reasons, source="regime")
        if regime_confidence < REGIME_CONFIDENCE_MIN:
            fallback_reasons.append("regime_confidence_low")
            regime = "neutral"

        anomaly_score = self._coerce_score(payload.get("anomalyScore"), fallback_reasons, source="anomaly")
        anomaly_confidence = self._coerce_confidence(payload.get("anomalyConfidence"), fallback_reasons, source="anomaly")

        raw_flag = payload.get("anomalyFlag")
        if isinstance(raw_flag, bool):
            anomaly_flag = raw_flag
        else:
            anomaly_flag = False
            fallback_reasons.append("anomaly_flag_missing")

        anomaly_breach = False
        if anomaly_flag and anomaly_score >= ANOMALY_BREACH_SCORE:
            if anomaly_confidence >= ANOMALY_BREACH_CONFIDENCE:
                anomaly_breach = True
            else:
                fallback_reasons.append("anomaly_confidence_low")

        fallback_reason = None
        if fallback_reasons:
            fallback_reason = ",".join(dict.fromkeys(fallback_reasons))

        return MLRiskSignalContext(
            regime=regime,
            regime_confidence=regime_confidence,
            regime_multiplier=self._regime_multiplier(regime=regime, confidence=regime_confidence),
            anomaly_score=anomaly_score,
            anomaly_confidence=anomaly_confidence,
            anomaly_flag=anomaly_flag,
            anomaly_breach=anomaly_breach,
            source=source,
            fallback_reason=fallback_reason,
        )

    @staticmethod
    def _normalize_regime_label(raw: object, fallback_reasons: list[str]) -> str:
        if not isinstance(raw, str):
            fallback_reasons.append("regime_missing")
            return "neutral"
        normalized = raw.strip().lower()
        if normalized == "":
            fallback_reasons.append("regime_missing")
            return "neutral"
        mapped = REGIME_ALIASES.get(normalized, normalized.replace(" ", "_"))
        if mapped not in {"risk_on", "neutral", "risk_off"}:
            fallback_reasons.append("regime_invalid")
            return "neutral"
        return mapped

    @staticmethod
    def _coerce_score(raw: object, fallback_reasons: list[str], *, source: str) -> float:
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            fallback_reasons.append(f"{source}_score_missing")
            return 0.0
        numeric = float(raw)
        if not math.isfinite(numeric):
            fallback_reasons.append(f"{source}_score_invalid")
            return 0.0
        if numeric < 0.0 or numeric > 1.0:
            fallback_reasons.append(f"{source}_score_out_of_range")
            return 0.0
        return numeric

    @staticmethod
    def _coerce_confidence(raw: object, fallback_reasons: list[str], *, source: str) -> float:
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            fallback_reasons.append(f"{source}_confidence_missing")
            return 0.0
        numeric = float(raw)
        if not math.isfinite(numeric):
            fallback_reasons.append(f"{source}_confidence_invalid")
            return 0.0
        if numeric > 1.0:
            numeric = numeric / 100.0
        if numeric < 0.0 or numeric > 1.0:
            fallback_reasons.append(f"{source}_confidence_out_of_range")
            return 0.0
        return numeric

    @staticmethod
    def _regime_multiplier(*, regime: str, confidence: float) -> float:
        if confidence < REGIME_CONFIDENCE_MIN:
            return 1.0
        if regime == "risk_off":
            return 0.7
        return 1.0

    @staticmethod
    def _ml_risk_fallback(*, reason: str) -> MLRiskSignalContext:
        return MLRiskSignalContext(
            regime="neutral",
            regime_confidence=0.0,
            regime_multiplier=1.0,
            anomaly_score=0.0,
            anomaly_confidence=0.0,
            anomaly_flag=False,
            anomaly_breach=False,
            source="fallback",
            fallback_reason=reason,
        )

    @staticmethod
    def _ml_risk_metadata(ml_context: MLRiskSignalContext) -> dict[str, object]:
        return {
            "mlSignalSource": ml_context.source,
            "mlSignalFallbackReason": ml_context.fallback_reason,
            "mlSignalFallbackUsed": ml_context.used_fallback,
            "mlRegime": ml_context.regime,
            "mlRegimeConfidence": ml_context.regime_confidence,
            "mlRegimeSizingMultiplier": ml_context.regime_multiplier,
            "mlAnomalyScore": ml_context.anomaly_score,
            "mlAnomalyConfidence": ml_context.anomaly_confidence,
            "mlAnomalyFlag": ml_context.anomaly_flag,
            "mlAnomalyBreach": ml_context.anomaly_breach,
        }

    @staticmethod
    def _ensure_ml_anomaly_not_breached(*, context: RequestContext, ml_context: MLRiskSignalContext) -> None:
        if not ml_context.anomaly_breach:
            return
        raise PlatformAPIError(
            status_code=423,
            code="RISK_ML_ANOMALY_BREACH",
            message=(
                "ML anomaly breach is active; execution side effects are blocked "
                f"(score={ml_context.anomaly_score}, confidence={ml_context.anomaly_confidence})."
            ),
            request_id=context.request_id,
        )

    @staticmethod
    def _clamp(value: float, *, minimum: float, maximum: float) -> float:
        return max(minimum, min(value, maximum))

    def _record_allow(
        self,
        *,
        check_type: str,
        resource_type: str,
        resource_id: str | None,
        context: RequestContext,
        policy_version: str | None,
        policy_mode: str | None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._risk_audit_service.record_decision(
            decision="approved",
            check_type=check_type,
            resource_type=resource_type,
            resource_id=resource_id,
            context=context,
            policy_version=policy_version,
            policy_mode=policy_mode,
            metadata=metadata,
        )

    def _record_block(
        self,
        *,
        check_type: str,
        resource_type: str,
        resource_id: str | None,
        context: RequestContext,
        outcome_code: str,
        reason: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        policy = self._store.risk_policy
        policy_version = policy.get("version") if isinstance(policy, dict) else None
        policy_mode = policy.get("mode") if isinstance(policy, dict) else None
        self._risk_audit_service.record_decision(
            decision="blocked",
            check_type=check_type,
            resource_type=resource_type,
            resource_id=resource_id,
            context=context,
            policy_version=policy_version if isinstance(policy_version, str) else None,
            policy_mode=policy_mode if isinstance(policy_mode, str) else None,
            outcome_code=outcome_code,
            reason=reason,
            metadata=metadata,
        )
