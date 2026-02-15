"""Risk decision audit trail persistence (AG-RISK-04)."""

from __future__ import annotations

from src.platform_api.schemas_v1 import RequestContext
from src.platform_api.state_store import InMemoryStateStore, RiskAuditRecord


class RiskAuditService:
    """Persists machine-readable allow/block decisions for risk checks."""

    def __init__(self, *, store: InMemoryStateStore) -> None:
        self._store = store

    def record_decision(
        self,
        *,
        decision: str,
        check_type: str,
        resource_type: str,
        resource_id: str | None,
        context: RequestContext,
        policy_version: str | None = None,
        policy_mode: str | None = None,
        outcome_code: str | None = None,
        reason: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> RiskAuditRecord:
        record_id = self._store.next_id("risk_audit")
        record = RiskAuditRecord(
            id=record_id,
            decision=decision,
            check_type=check_type,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            policy_version=policy_version,
            policy_mode=policy_mode,
            outcome_code=outcome_code,
            reason=reason,
            metadata=dict(metadata or {}),
        )
        self._store.risk_audit_trail[record.id] = record
        return record
