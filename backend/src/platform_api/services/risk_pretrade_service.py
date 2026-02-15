"""Pre-trade risk gate for execution side-effecting commands (AG-RISK-02)."""

from __future__ import annotations

from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import CreateDeploymentRequest, CreateOrderRequest, RequestContext
from src.platform_api.services.risk_audit_service import RiskAuditService
from src.platform_api.services.risk_policy import RiskPolicyValidationError, validate_risk_policy
from src.platform_api.state_store import InMemoryStateStore

_ACTIVE_DEPLOYMENT_STATES = {"queued", "running", "paused"}


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
        try:
            policy = self._validated_policy(context=context)
            if policy.mode == "advisory":
                self._record_allow(
                    check_type="pretrade_deployment",
                    resource_type="deployment",
                    resource_id=request.strategyId,
                    context=context,
                    policy_version=policy.version,
                    policy_mode=policy.mode,
                    metadata={"capital": request.capital, "mode": request.mode, "reason": "advisory_mode"},
                )
                return
            self._ensure_kill_switch_not_triggered(context=context)

            active_deployment_capital = sum(
                deployment.capital
                for deployment in self._store.deployments.values()
                if deployment.status in _ACTIVE_DEPLOYMENT_STATES
            )
            projected_total = active_deployment_capital + request.capital

            if request.capital > policy.limits.maxNotionalUsd:
                raise self._limit_breach(
                    context=context,
                    message=(
                        "Deployment capital exceeds risk maxNotionalUsd "
                        f"({request.capital} > {policy.limits.maxNotionalUsd})."
                    ),
                )
            if projected_total > policy.limits.maxNotionalUsd:
                raise self._limit_breach(
                    context=context,
                    message=(
                        "Projected active deployment capital exceeds risk maxNotionalUsd "
                        f"({projected_total} > {policy.limits.maxNotionalUsd})."
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
                metadata={"capital": request.capital, "mode": request.mode},
            )
            raise

    def ensure_order_allowed(
        self,
        *,
        request: CreateOrderRequest,
        context: RequestContext,
    ) -> None:
        try:
            policy = self._validated_policy(context=context)
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

            if projected_symbol_notional > policy.limits.maxPositionNotionalUsd:
                raise self._limit_breach(
                    context=context,
                    message=(
                        "Projected symbol notional exceeds risk maxPositionNotionalUsd "
                        f"({projected_symbol_notional} > {policy.limits.maxPositionNotionalUsd})."
                    ),
                )

            if order_notional > policy.limits.maxNotionalUsd:
                raise self._limit_breach(
                    context=context,
                    message=(
                        "Order notional exceeds risk maxNotionalUsd "
                        f"({order_notional} > {policy.limits.maxNotionalUsd})."
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
            if projected_notional > policy.limits.maxNotionalUsd:
                raise self._limit_breach(
                    context=context,
                    message=(
                        "Projected total notional exceeds risk maxNotionalUsd "
                        f"({projected_notional} > {policy.limits.maxNotionalUsd})."
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
