"""Execution adapter contract and in-memory baseline."""

from __future__ import annotations

from typing import Protocol

from src.platform_api.state_store import (
    DeploymentRecord,
    InMemoryStateStore,
    OrderRecord,
    PortfolioRecord,
    utc_now,
)


class ExecutionAdapter(Protocol):
    """Provider-facing execution contract for deployments, orders, and portfolios."""

    async def create_deployment(
        self,
        *,
        strategy_id: str,
        mode: str,
        capital: float,
        tenant_id: str,
        user_id: str,
        idempotency_key: str,
    ) -> dict[str, str]:
        ...

    async def stop_deployment(
        self,
        *,
        provider_deployment_id: str,
        reason: str | None,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, str]:
        ...

    async def get_deployment(
        self,
        *,
        provider_deployment_id: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, float | str | None]:
        ...

    async def list_deployments(self, *, status: str | None) -> list[DeploymentRecord]:
        ...

    async def place_order(
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
    ) -> dict[str, str]:
        ...

    async def cancel_order(
        self,
        *,
        provider_order_id: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, str]:
        ...

    async def get_order(self, *, provider_order_id: str, tenant_id: str, user_id: str) -> OrderRecord | None:
        ...

    async def list_orders(self, *, status: str | None) -> list[OrderRecord]:
        ...

    async def get_portfolio_snapshot(self, *, portfolio_id: str, tenant_id: str, user_id: str) -> PortfolioRecord | None:
        ...

    async def list_portfolios(self) -> list[PortfolioRecord]:
        ...


class InMemoryExecutionAdapter:
    """Execution adapter baseline that behaves like an external engine via memory state."""

    def __init__(self, store: InMemoryStateStore) -> None:
        self._store = store

    async def create_deployment(
        self,
        *,
        strategy_id: str,
        mode: str,
        capital: float,
        tenant_id: str,
        user_id: str,
        idempotency_key: str,
    ) -> dict[str, str]:
        deployment_id = self._store.next_id("deployment")
        provider_ref_id = f"live-{deployment_id}"
        now = utc_now()
        self._store.deployments[deployment_id] = DeploymentRecord(
            id=deployment_id,
            strategy_id=strategy_id,
            mode=mode,
            status="queued",
            capital=capital,
            provider_ref_id=provider_ref_id,
            latest_pnl=None,
            created_at=now,
            updated_at=now,
        )
        return {
            "providerDeploymentId": provider_ref_id,
            "deploymentId": deployment_id,
            "status": "queued",
        }

    async def stop_deployment(
        self,
        *,
        provider_deployment_id: str,
        reason: str | None,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, str]:
        deployment = self._find_deployment_by_provider_ref(provider_deployment_id)
        if deployment is None:
            return {"status": "failed"}
        deployment.status = "stopping"
        deployment.updated_at = utc_now()
        return {"status": "stopping"}

    async def get_deployment(
        self,
        *,
        provider_deployment_id: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, float | str | None]:
        deployment = self._find_deployment_by_provider_ref(provider_deployment_id)
        if deployment is None:
            return {"status": "failed", "latestPnl": None}
        return {
            "status": deployment.status,
            "latestPnl": deployment.latest_pnl,
        }

    async def list_deployments(self, *, status: str | None) -> list[DeploymentRecord]:
        items = list(self._store.deployments.values())
        if status:
            items = [item for item in items if item.status == status]
        return items

    async def place_order(
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
    ) -> dict[str, str]:
        order_id = self._store.next_id("order")
        provider_order_id = f"live-order-{order_id}"
        self._store.orders[order_id] = OrderRecord(
            id=order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            status="pending",
            deployment_id=deployment_id,
            provider_order_id=provider_order_id,
            created_at=utc_now(),
        )
        return {
            "providerOrderId": provider_order_id,
            "orderId": order_id,
            "status": "pending",
        }

    async def cancel_order(
        self,
        *,
        provider_order_id: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, str]:
        order = self._find_order_by_provider_ref(provider_order_id)
        if order is None:
            return {"status": "failed"}
        order.status = "cancelled"
        return {"status": "cancelled"}

    async def get_order(self, *, provider_order_id: str, tenant_id: str, user_id: str) -> OrderRecord | None:
        return self._find_order_by_provider_ref(provider_order_id)

    async def list_orders(self, *, status: str | None) -> list[OrderRecord]:
        items = list(self._store.orders.values())
        if status:
            items = [item for item in items if item.status == status]
        return items

    async def get_portfolio_snapshot(self, *, portfolio_id: str, tenant_id: str, user_id: str) -> PortfolioRecord | None:
        return self._store.portfolios.get(portfolio_id)

    async def list_portfolios(self) -> list[PortfolioRecord]:
        return list(self._store.portfolios.values())

    def _find_deployment_by_provider_ref(self, provider_ref_id: str) -> DeploymentRecord | None:
        for deployment in self._store.deployments.values():
            if deployment.provider_ref_id == provider_ref_id:
                return deployment
        return None

    def _find_order_by_provider_ref(self, provider_order_id: str) -> OrderRecord | None:
        for order in self._store.orders.values():
            if order.provider_order_id == provider_order_id:
                return order
        return None


def deployment_to_dict(record: DeploymentRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "strategyId": record.strategy_id,
        "mode": record.mode,
        "status": record.status,
        "capital": record.capital,
        "engine": record.engine,
        "providerRefId": record.provider_ref_id,
        "latestPnl": record.latest_pnl,
        "createdAt": record.created_at,
        "updatedAt": record.updated_at,
    }


def order_to_dict(record: OrderRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "symbol": record.symbol,
        "side": record.side,
        "type": record.order_type,
        "quantity": record.quantity,
        "price": record.price,
        "status": record.status,
        "deploymentId": record.deployment_id,
        "createdAt": record.created_at,
    }


def portfolio_to_dict(record: PortfolioRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "mode": record.mode,
        "cash": record.cash,
        "totalValue": record.total_value,
        "pnlTotal": record.pnl_total,
        "positions": [
            {
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "avgPrice": pos.avg_price,
                "currentPrice": pos.current_price,
                "unrealizedPnl": pos.unrealized_pnl,
            }
            for pos in record.positions
        ],
    }
