"""Contract tests for bounded reconciliation policy in ExecutionService list endpoints."""

from __future__ import annotations

import asyncio

from src.platform_api.schemas_v1 import RequestContext
from src.platform_api.services.execution_service import ExecutionService
from src.platform_api.state_store import InMemoryStateStore


class _StubExecutionAdapter:
    async def list_deployments(self, *, status: str | None):  # type: ignore[no-untyped-def]
        _ = status
        return []

    async def list_orders(self, *, status: str | None):  # type: ignore[no-untyped-def]
        _ = status
        return []


class _StubReconciliationService:
    def __init__(self) -> None:
        self.deployment_runs = 0
        self.order_runs = 0

    async def run_deployment_drift_checks(  # type: ignore[no-untyped-def]
        self,
        *,
        tenant_id: str,
        user_id: str,
        request_id: str | None = None,
    ):
        _ = (tenant_id, user_id, request_id)
        self.deployment_runs += 1
        return None

    async def run_order_drift_checks(  # type: ignore[no-untyped-def]
        self,
        *,
        tenant_id: str,
        user_id: str,
        request_id: str | None = None,
    ):
        _ = (tenant_id, user_id, request_id)
        self.order_runs += 1
        return None

    async def run_drift_checks(self, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("ExecutionService should not call full run_drift_checks for list endpoints.")


async def _exercise_list_reconciliation_policy() -> None:
    store = InMemoryStateStore()
    reconciliation = _StubReconciliationService()
    service = ExecutionService(
        store=store,
        execution_adapter=_StubExecutionAdapter(),
        reconciliation_service=reconciliation,
        reconciliation_min_interval_seconds=30.0,
    )
    context = RequestContext(
        request_id="req-policy-001",
        tenant_id="tenant-a",
        user_id="user-a",
    )

    await service.list_deployments(status=None, cursor=None, context=context)
    await service.list_deployments(status=None, cursor=None, context=context)
    await service.list_orders(status=None, cursor=None, context=context)
    await service.list_orders(status=None, cursor=None, context=context)

    assert reconciliation.deployment_runs == 1
    assert reconciliation.order_runs == 1


def test_list_endpoints_use_scoped_throttled_reconciliation() -> None:
    asyncio.run(_exercise_list_reconciliation_policy())
