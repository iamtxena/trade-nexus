"""Execution command layer enforcing adapter-only side effects (AG-EXE-01)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.platform_api.adapters.execution_adapter import ExecutionAdapter
from src.platform_api.errors import PlatformAPIError
from src.platform_api.state_store import InMemoryStateStore


@dataclass(frozen=True)
class CreateDeploymentCommand:
    strategy_id: str
    mode: str
    capital: float
    tenant_id: str
    user_id: str
    idempotency_key: str
    request_id: str | None = None


@dataclass(frozen=True)
class StopDeploymentCommand:
    provider_deployment_id: str
    reason: str | None
    tenant_id: str
    user_id: str


@dataclass(frozen=True)
class PlaceOrderCommand:
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None
    deployment_id: str | None
    tenant_id: str
    user_id: str
    idempotency_key: str
    request_id: str | None = None


@dataclass(frozen=True)
class CancelOrderCommand:
    provider_order_id: str
    tenant_id: str
    user_id: str


class ExecutionCommandService:
    """Executes side-effecting commands exclusively through ExecutionAdapter."""

    def __init__(
        self,
        *,
        execution_adapter: ExecutionAdapter,
        store: InMemoryStateStore | None = None,
    ) -> None:
        self._execution_adapter = execution_adapter
        self._store = store

    async def create_deployment(self, *, command: CreateDeploymentCommand) -> dict[str, Any]:
        payload = {
            "strategyId": command.strategy_id,
            "mode": command.mode,
            "capital": command.capital,
            "tenantId": command.tenant_id,
            "userId": command.user_id,
        }
        cached = self._load_idempotent(
            scope="execution_commands_deployments",
            key=command.idempotency_key,
            payload=payload,
            request_id=command.request_id,
        )
        if cached is not None:
            return cached

        response = await self._execution_adapter.create_deployment(
            strategy_id=command.strategy_id,
            mode=command.mode,
            capital=command.capital,
            tenant_id=command.tenant_id,
            user_id=command.user_id,
            idempotency_key=command.idempotency_key,
        )
        self._save_idempotent(
            scope="execution_commands_deployments",
            key=command.idempotency_key,
            payload=payload,
            response=response,
        )
        return response

    async def stop_deployment(self, *, command: StopDeploymentCommand) -> dict[str, Any]:
        return await self._execution_adapter.stop_deployment(
            provider_deployment_id=command.provider_deployment_id,
            reason=command.reason,
            tenant_id=command.tenant_id,
            user_id=command.user_id,
        )

    async def place_order(self, *, command: PlaceOrderCommand) -> dict[str, Any]:
        payload = {
            "symbol": command.symbol,
            "side": command.side,
            "type": command.order_type,
            "quantity": command.quantity,
            "price": command.price,
            "deploymentId": command.deployment_id,
            "tenantId": command.tenant_id,
            "userId": command.user_id,
        }
        cached = self._load_idempotent(
            scope="execution_commands_orders",
            key=command.idempotency_key,
            payload=payload,
            request_id=command.request_id,
        )
        if cached is not None:
            return cached

        response = await self._execution_adapter.place_order(
            symbol=command.symbol,
            side=command.side,
            order_type=command.order_type,
            quantity=command.quantity,
            price=command.price,
            deployment_id=command.deployment_id,
            tenant_id=command.tenant_id,
            user_id=command.user_id,
            idempotency_key=command.idempotency_key,
        )
        self._save_idempotent(
            scope="execution_commands_orders",
            key=command.idempotency_key,
            payload=payload,
            response=response,
        )
        return response

    async def cancel_order(self, *, command: CancelOrderCommand) -> dict[str, Any]:
        return await self._execution_adapter.cancel_order(
            provider_order_id=command.provider_order_id,
            tenant_id=command.tenant_id,
            user_id=command.user_id,
        )

    def _load_idempotent(
        self,
        *,
        scope: str,
        key: str,
        payload: dict[str, Any],
        request_id: str | None,
    ) -> dict[str, Any] | None:
        if self._store is None:
            return None
        conflict, cached = self._store.get_idempotent_response(
            scope=scope,
            key=key,
            payload=payload,
        )
        if conflict:
            raise PlatformAPIError(
                status_code=409,
                code="IDEMPOTENCY_KEY_CONFLICT",
                message="Idempotency-Key reused with different execution command payload.",
                request_id=request_id,
            )
        return cached

    def _save_idempotent(
        self,
        *,
        scope: str,
        key: str,
        payload: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        if self._store is None:
            return
        self._store.save_idempotent_response(
            scope=scope,
            key=key,
            payload=payload,
            response=response,
        )
