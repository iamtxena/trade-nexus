"""Drawdown breach handling and kill-switch activation (AG-RISK-03)."""

from __future__ import annotations

from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import RequestContext
from src.platform_api.services.risk_policy import RiskPolicyValidationError, validate_risk_policy
from src.platform_api.state_store import InMemoryStateStore, utc_now


class RiskKillSwitchService:
    """Evaluates runtime drawdown and mutates kill-switch state on breaches."""

    def __init__(self, *, store: InMemoryStateStore) -> None:
        self._store = store

    def evaluate_drawdown_breach(
        self,
        *,
        deployment_id: str,
        capital: float,
        latest_pnl: float | None,
        context: RequestContext,
    ) -> bool:
        policy = self._validated_policy(context=context)
        if policy.mode != "enforced":
            return False

        kill_switch = self._store.risk_policy.get("killSwitch")
        if not isinstance(kill_switch, dict):
            return False
        if not bool(kill_switch.get("enabled")):
            return False
        if bool(kill_switch.get("triggered")):
            return True
        if latest_pnl is None or capital <= 0:
            return False
        if latest_pnl >= 0:
            return False

        drawdown_pct = (abs(latest_pnl) / capital) * 100
        if drawdown_pct < policy.limits.maxDrawdownPct:
            return False

        kill_switch["triggered"] = True
        kill_switch["triggeredAt"] = utc_now()
        kill_switch["reason"] = (
            f"Deployment {deployment_id} drawdown {drawdown_pct:.2f}% breached limit "
            f"{policy.limits.maxDrawdownPct:.2f}%."
        )
        return True

    def kill_switch_reason(self) -> str | None:
        kill_switch = self._store.risk_policy.get("killSwitch")
        if not isinstance(kill_switch, dict):
            return None
        reason = kill_switch.get("reason")
        if isinstance(reason, str) and reason.strip():
            return reason
        return None

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
