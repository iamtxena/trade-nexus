"""Execution command layer enforcing adapter-only side effects (AG-EXE-01)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.platform_api.adapters.execution_adapter import ExecutionAdapter


@dataclass(frozen=True)
class CreateDeploymentCommand:
    strategy_id: str
    mode: str
    capital: float
    tenant_id: str
    user_id: str
    idempotency_key: str


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


@dataclass(frozen=True)
class CancelOrderCommand:
    provider_order_id: str
    tenant_id: str
    user_id: str


class ExecutionCommandService:
    """Executes side-effecting commands exclusively through ExecutionAdapter."""

    def __init__(self, *, execution_adapter: ExecutionAdapter) -> None:
        self._execution_adapter = execution_adapter

    async def create_deployment(self, *, command: CreateDeploymentCommand) -> dict[str, Any]:
        return await self._execution_adapter.create_deployment(
            strategy_id=command.strategy_id,
            mode=command.mode,
            capital=command.capital,
            tenant_id=command.tenant_id,
            user_id=command.user_id,
            idempotency_key=command.idempotency_key,
        )

    async def stop_deployment(self, *, command: StopDeploymentCommand) -> dict[str, Any]:
        return await self._execution_adapter.stop_deployment(
            provider_deployment_id=command.provider_deployment_id,
            reason=command.reason,
            tenant_id=command.tenant_id,
            user_id=command.user_id,
        )

    async def place_order(self, *, command: PlaceOrderCommand) -> dict[str, Any]:
        return await self._execution_adapter.place_order(
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

    async def cancel_order(self, *, command: CancelOrderCommand) -> dict[str, Any]:
        return await self._execution_adapter.cancel_order(
            provider_order_id=command.provider_order_id,
            tenant_id=command.tenant_id,
            user_id=command.user_id,
        )
