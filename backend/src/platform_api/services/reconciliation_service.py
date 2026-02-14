"""Deployment/order reconciliation and drift detection."""

from __future__ import annotations

from dataclasses import dataclass

from src.platform_api.adapters.execution_adapter import ExecutionAdapter
from src.platform_api.services.execution_lifecycle_mapping import apply_deployment_transition
from src.platform_api.state_store import DriftEventRecord, InMemoryStateStore, utc_now


@dataclass
class ReconciliationSummary:
    deployment_checks: int
    order_checks: int
    drift_count: int


class ReconciliationService:
    """Reconcile platform state with provider state and record drift events."""

    def __init__(self, *, store: InMemoryStateStore, execution_adapter: ExecutionAdapter) -> None:
        self._store = store
        self._execution_adapter = execution_adapter

    async def reconcile_deployments(
        self,
        *,
        tenant_id: str,
        user_id: str,
        request_id: str | None = None,
    ) -> list[DriftEventRecord]:
        events: list[DriftEventRecord] = []
        for deployment in self._store.deployments.values():
            if not deployment.provider_ref_id:
                continue
            provider = await self._execution_adapter.get_deployment(
                provider_deployment_id=deployment.provider_ref_id,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            provider_status = str(provider.get("status", "failed"))
            next_status = apply_deployment_transition(deployment.status, provider_status)
            provider_pnl = provider.get("latestPnl")
            pnl_changed = isinstance(provider_pnl, (int, float)) and deployment.latest_pnl != float(provider_pnl)

            if next_status != deployment.status or pnl_changed:
                previous_state = deployment.status
                deployment.status = next_status
                if isinstance(provider_pnl, (int, float)):
                    deployment.latest_pnl = float(provider_pnl)
                deployment.updated_at = utc_now()
                events.append(
                    self._record_drift(
                        resource_type="deployment",
                        resource_id=deployment.id,
                        provider_ref_id=deployment.provider_ref_id,
                        previous_state=previous_state,
                        provider_state=provider_status,
                        resolution=f"mapped_to_{next_status}",
                        tenant_id=tenant_id,
                        user_id=user_id,
                        request_id=request_id,
                        metadata={"latestPnl": deployment.latest_pnl},
                    )
                )
        return events

    async def reconcile_orders(
        self,
        *,
        tenant_id: str,
        user_id: str,
        request_id: str | None = None,
    ) -> list[DriftEventRecord]:
        events: list[DriftEventRecord] = []
        for order in self._store.orders.values():
            if not order.provider_order_id:
                continue
            provider_order = await self._execution_adapter.get_order(
                provider_order_id=order.provider_order_id,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            if provider_order is None:
                continue
            provider_state = provider_order.status
            if provider_state != order.status:
                previous_state = order.status
                order.status = provider_state
                events.append(
                    self._record_drift(
                        resource_type="order",
                        resource_id=order.id,
                        provider_ref_id=order.provider_order_id,
                        previous_state=previous_state,
                        provider_state=provider_state,
                        resolution=f"synced_to_{provider_state}",
                        tenant_id=tenant_id,
                        user_id=user_id,
                        request_id=request_id,
                    )
                )
        return events

    async def run_drift_checks(
        self,
        *,
        tenant_id: str,
        user_id: str,
        request_id: str | None = None,
    ) -> ReconciliationSummary:
        deployment_events = await self.reconcile_deployments(
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
        )
        order_events = await self.reconcile_orders(
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
        )
        return ReconciliationSummary(
            deployment_checks=len(self._store.deployments),
            order_checks=len(self._store.orders),
            drift_count=len(deployment_events) + len(order_events),
        )

    def _record_drift(
        self,
        *,
        resource_type: str,
        resource_id: str,
        provider_ref_id: str | None,
        previous_state: str,
        provider_state: str,
        resolution: str,
        tenant_id: str,
        user_id: str,
        request_id: str | None,
        metadata: dict[str, object] | None = None,
    ) -> DriftEventRecord:
        event_metadata = {
            "tenantId": tenant_id,
            "userId": user_id,
        }
        if request_id:
            event_metadata["requestId"] = request_id
        event_metadata.update(dict(metadata or {}))
        event = DriftEventRecord(
            id=self._store.next_id("drift"),
            resource_type=resource_type,
            resource_id=resource_id,
            provider_ref_id=provider_ref_id,
            previous_state=previous_state,
            provider_state=provider_state,
            resolution=resolution,
            metadata=event_metadata,
        )
        self._store.drift_events[event.id] = event
        return event
