"""Drawdown breach handling and kill-switch activation (AG-RISK-03)."""

from __future__ import annotations

from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import RequestContext
from src.platform_api.services.risk_audit_service import RiskAuditService
from src.platform_api.services.risk_policy import RiskPolicyValidationError, validate_risk_policy
from src.platform_api.state_store import InMemoryStateStore, utc_now


class RiskKillSwitchService:
    """Evaluates runtime drawdown and mutates kill-switch state on breaches."""

    def __init__(self, *, store: InMemoryStateStore) -> None:
        self._store = store
        self._risk_audit_service = RiskAuditService(store=store)

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
            self._record_approved(
                deployment_id=deployment_id,
                context=context,
                policy_version=policy.version,
                policy_mode=policy.mode,
                metadata={"reason": "advisory_mode", "latestPnl": latest_pnl, "capital": capital},
            )
            return False

        kill_switch = self._store.risk_policy.get("killSwitch")
        if not isinstance(kill_switch, dict) or not bool(kill_switch.get("enabled")):
            self._record_approved(
                deployment_id=deployment_id,
                context=context,
                policy_version=policy.version,
                policy_mode=policy.mode,
                metadata={"reason": "kill_switch_disabled", "latestPnl": latest_pnl, "capital": capital},
            )
            return False
        if bool(kill_switch.get("triggered")):
            self._record_blocked(
                deployment_id=deployment_id,
                context=context,
                policy_version=policy.version,
                policy_mode=policy.mode,
                outcome_code="RISK_KILL_SWITCH_ACTIVE",
                reason="Kill-switch already active from prior risk breach.",
                metadata={"latestPnl": latest_pnl, "capital": capital},
            )
            return True
        if latest_pnl is None or capital <= 0:
            self._record_approved(
                deployment_id=deployment_id,
                context=context,
                policy_version=policy.version,
                policy_mode=policy.mode,
                metadata={"reason": "insufficient_runtime_data", "latestPnl": latest_pnl, "capital": capital},
            )
            return False
        if latest_pnl >= 0:
            self._record_approved(
                deployment_id=deployment_id,
                context=context,
                policy_version=policy.version,
                policy_mode=policy.mode,
                metadata={"reason": "non_negative_pnl", "latestPnl": latest_pnl, "capital": capital},
            )
            return False

        drawdown_pct = (abs(latest_pnl) / capital) * 100
        if drawdown_pct < policy.limits.maxDrawdownPct:
            self._record_approved(
                deployment_id=deployment_id,
                context=context,
                policy_version=policy.version,
                policy_mode=policy.mode,
                metadata={
                    "drawdownPct": drawdown_pct,
                    "limitPct": policy.limits.maxDrawdownPct,
                    "latestPnl": latest_pnl,
                    "capital": capital,
                },
            )
            return False

        kill_switch["triggered"] = True
        kill_switch["triggeredAt"] = utc_now()
        kill_switch["reason"] = (
            f"Deployment {deployment_id} drawdown {drawdown_pct:.2f}% breached limit "
            f"{policy.limits.maxDrawdownPct:.2f}%."
        )
        self._record_blocked(
            deployment_id=deployment_id,
            context=context,
            policy_version=policy.version,
            policy_mode=policy.mode,
            outcome_code="RISK_DRAWDOWN_BREACH",
            reason=str(kill_switch["reason"]),
            metadata={
                "drawdownPct": drawdown_pct,
                "limitPct": policy.limits.maxDrawdownPct,
                "latestPnl": latest_pnl,
                "capital": capital,
            },
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
            self._record_invalid_policy(context=context, reason=str(exc))
            raise PlatformAPIError(
                status_code=500,
                code="RISK_POLICY_INVALID",
                message=f"Risk policy validation failed: {exc}",
                request_id=context.request_id,
            ) from exc

    def _record_approved(
        self,
        *,
        deployment_id: str,
        context: RequestContext,
        policy_version: str | None,
        policy_mode: str | None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._risk_audit_service.record_decision(
            decision="approved",
            check_type="runtime_drawdown",
            resource_type="deployment",
            resource_id=deployment_id,
            context=context,
            policy_version=policy_version,
            policy_mode=policy_mode,
            metadata=metadata,
        )

    def _record_blocked(
        self,
        *,
        deployment_id: str,
        context: RequestContext,
        policy_version: str | None,
        policy_mode: str | None,
        outcome_code: str,
        reason: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._risk_audit_service.record_decision(
            decision="blocked",
            check_type="runtime_drawdown",
            resource_type="deployment",
            resource_id=deployment_id,
            context=context,
            policy_version=policy_version,
            policy_mode=policy_mode,
            outcome_code=outcome_code,
            reason=reason,
            metadata=metadata,
        )

    def _record_invalid_policy(self, *, context: RequestContext, reason: str) -> None:
        policy = self._store.risk_policy
        version = policy.get("version") if isinstance(policy, dict) else None
        mode = policy.get("mode") if isinstance(policy, dict) else None
        self._risk_audit_service.record_decision(
            decision="blocked",
            check_type="runtime_drawdown",
            resource_type="deployment",
            resource_id=None,
            context=context,
            policy_version=version if isinstance(version, str) else None,
            policy_mode=mode if isinstance(mode, str) else None,
            outcome_code="RISK_POLICY_INVALID",
            reason=reason,
        )
