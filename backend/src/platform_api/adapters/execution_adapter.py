"""Execution adapter contract and in-memory baseline."""

from __future__ import annotations

from typing import Any
from typing import Protocol

import httpx

from src.platform_api.adapters.lona_adapter import AdapterError
from src.platform_api.state_store import (
    DeploymentRecord,
    InMemoryStateStore,
    OrderRecord,
    PortfolioRecord,
    PositionRecord,
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

    async def list_deployments(
        self,
        *,
        status: str | None,
        tenant_id: str,
        user_id: str,
    ) -> list[DeploymentRecord]:
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

    async def list_orders(
        self,
        *,
        status: str | None,
        tenant_id: str,
        user_id: str,
    ) -> list[OrderRecord]:
        ...

    async def get_portfolio_snapshot(self, *, portfolio_id: str, tenant_id: str, user_id: str) -> PortfolioRecord | None:
        ...

    async def list_portfolios(
        self,
        *,
        tenant_id: str,
        user_id: str,
    ) -> list[PortfolioRecord]:
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
        if deployment.status in {"failed", "stopped"}:
            next_status = deployment.status
        else:
            next_status = "stopping"
        deployment.status = next_status
        deployment.updated_at = utc_now()
        return {"status": next_status}

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

    async def list_deployments(
        self,
        *,
        status: str | None,
        tenant_id: str,
        user_id: str,
    ) -> list[DeploymentRecord]:
        _ = (tenant_id, user_id)
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

    async def list_orders(
        self,
        *,
        status: str | None,
        tenant_id: str,
        user_id: str,
    ) -> list[OrderRecord]:
        _ = (tenant_id, user_id)
        items = list(self._store.orders.values())
        if status:
            items = [item for item in items if item.status == status]
        return items

    async def get_portfolio_snapshot(self, *, portfolio_id: str, tenant_id: str, user_id: str) -> PortfolioRecord | None:
        return self._store.portfolios.get(portfolio_id)

    async def list_portfolios(
        self,
        *,
        tenant_id: str,
        user_id: str,
    ) -> list[PortfolioRecord]:
        _ = (tenant_id, user_id)
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


class LiveEngineExecutionAdapter:
    """Execution adapter that delegates to live-engine internal service routes."""

    def __init__(
        self,
        *,
        base_url: str,
        service_api_key: str,
        timeout_seconds: float = 8.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_api_key = service_api_key
        self._timeout_seconds = timeout_seconds

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
        payload = {
            "strategyId": strategy_id,
            "mode": mode,
            "capital": capital,
            "idempotencyKey": idempotency_key,
        }
        body = await self._request(
            method="POST",
            path="/api/internal/deployments",
            payload=payload,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        deployment = body.get("deployment")
        if not isinstance(deployment, dict):
            raise AdapterError("Invalid deployment payload from live-engine.", code="LIVE_ENGINE_BAD_RESPONSE")
        return {
            "providerDeploymentId": str(deployment.get("providerRefId", deployment.get("id"))),
            "deploymentId": str(deployment.get("id")),
            "status": str(deployment.get("status", "queued")),
        }

    async def stop_deployment(
        self,
        *,
        provider_deployment_id: str,
        reason: str | None,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, str]:
        payload: dict[str, str] | None = {"reason": reason} if reason else None
        body = await self._request(
            method="POST",
            path=f"/api/internal/deployments/{provider_deployment_id}/stop",
            payload=payload,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        deployment = body.get("deployment")
        if not isinstance(deployment, dict):
            return {"status": "failed"}
        return {"status": str(deployment.get("status", "failed"))}

    async def get_deployment(
        self,
        *,
        provider_deployment_id: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, float | str | None]:
        body = await self._request(
            method="GET",
            path=f"/api/internal/deployments/{provider_deployment_id}",
            payload=None,
            tenant_id=tenant_id,
            user_id=user_id,
            allow_not_found=True,
        )
        if body is None:
            return {"status": "failed", "latestPnl": None}
        deployment = body.get("deployment")
        if not isinstance(deployment, dict):
            return {"status": "failed", "latestPnl": None}
        latest_pnl = deployment.get("latestPnl")
        return {"status": str(deployment.get("status", "failed")), "latestPnl": latest_pnl if isinstance(latest_pnl, (int, float)) else None}

    async def list_deployments(
        self,
        *,
        status: str | None,
        tenant_id: str,
        user_id: str,
    ) -> list[DeploymentRecord]:
        query = f"?status={status}" if status else ""
        body = await self._request(
            method="GET",
            path=f"/api/internal/deployments{query}",
            payload=None,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        deployments = body.get("items")
        if not isinstance(deployments, list):
            return []
        return [self._to_deployment_record(item) for item in deployments if isinstance(item, dict)]

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
        payload = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
            "price": price,
            "deploymentId": deployment_id,
            "idempotencyKey": idempotency_key,
        }
        body = await self._request(
            method="POST",
            path="/api/internal/orders",
            payload=payload,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        order = body.get("order")
        if not isinstance(order, dict):
            raise AdapterError("Invalid order payload from live-engine.", code="LIVE_ENGINE_BAD_RESPONSE")
        return {
            "providerOrderId": str(order.get("providerOrderId", order.get("id"))),
            "orderId": str(order.get("id")),
            "status": str(order.get("status", "pending")),
        }

    async def cancel_order(
        self,
        *,
        provider_order_id: str,
        tenant_id: str,
        user_id: str,
    ) -> dict[str, str]:
        body = await self._request(
            method="DELETE",
            path=f"/api/internal/orders/{provider_order_id}",
            payload=None,
            tenant_id=tenant_id,
            user_id=user_id,
            allow_not_found=True,
        )
        if body is None:
            return {"status": "failed"}
        order = body.get("order")
        if not isinstance(order, dict):
            return {"status": "failed"}
        return {"status": str(order.get("status", "cancelled"))}

    async def get_order(self, *, provider_order_id: str, tenant_id: str, user_id: str) -> OrderRecord | None:
        body = await self._request(
            method="GET",
            path=f"/api/internal/orders/{provider_order_id}",
            payload=None,
            tenant_id=tenant_id,
            user_id=user_id,
            allow_not_found=True,
        )
        if body is None:
            return None
        order = body.get("order")
        if not isinstance(order, dict):
            return None
        return self._to_order_record(order)

    async def list_orders(
        self,
        *,
        status: str | None,
        tenant_id: str,
        user_id: str,
    ) -> list[OrderRecord]:
        query = f"?status={status}" if status else ""
        body = await self._request(
            method="GET",
            path=f"/api/internal/orders{query}",
            payload=None,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        orders = body.get("items")
        if not isinstance(orders, list):
            return []
        return [self._to_order_record(item) for item in orders if isinstance(item, dict)]

    async def get_portfolio_snapshot(self, *, portfolio_id: str, tenant_id: str, user_id: str) -> PortfolioRecord | None:
        body = await self._request(
            method="GET",
            path=f"/api/internal/portfolios/{portfolio_id}",
            payload=None,
            tenant_id=tenant_id,
            user_id=user_id,
            allow_not_found=True,
        )
        if body is None:
            return None
        portfolio = body.get("portfolio")
        if not isinstance(portfolio, dict):
            return None
        return self._to_portfolio_record(portfolio)

    async def list_portfolios(
        self,
        *,
        tenant_id: str,
        user_id: str,
    ) -> list[PortfolioRecord]:
        body = await self._request(
            method="GET",
            path="/api/internal/portfolios",
            payload=None,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        portfolios = body.get("items")
        if not isinstance(portfolios, list):
            return []
        return [self._to_portfolio_record(item) for item in portfolios if isinstance(item, dict)]

    async def _request(
        self,
        *,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        tenant_id: str,
        user_id: str,
        allow_not_found: bool = False,
    ) -> dict[str, Any] | None:
        headers = {
            "Authorization": f"Bearer {self._service_api_key}",
            "X-Tenant-Id": tenant_id,
            "X-User-Id": user_id,
            "X-Request-Id": f"req-adapter-{utc_now()}",
        }
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            try:
                response = await client.request(
                    method=method,
                    url=f"{self._base_url}{path}",
                    headers=headers,
                    json=payload,
                )
            except httpx.HTTPError as exc:
                raise AdapterError(str(exc), code="LIVE_ENGINE_UNAVAILABLE", status_code=502) from exc

        if response.status_code == 404 and allow_not_found:
            return None
        if response.status_code >= 400:
            raise AdapterError(
                response.text or "Live-engine request failed.",
                code="LIVE_ENGINE_REQUEST_FAILED",
                status_code=response.status_code,
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise AdapterError(
                "Live-engine response is not valid JSON.",
                code="LIVE_ENGINE_BAD_RESPONSE_JSON",
                status_code=502,
            ) from exc
        if not isinstance(body, dict):
            raise AdapterError("Live-engine response must be an object.", code="LIVE_ENGINE_BAD_RESPONSE")
        return body

    @staticmethod
    def _to_deployment_record(payload: dict[str, Any]) -> DeploymentRecord:
        return DeploymentRecord(
            id=str(payload.get("id")),
            strategy_id=str(payload.get("strategyId")),
            mode=str(payload.get("mode", "paper")),
            status=str(payload.get("status", "failed")),
            capital=float(payload.get("capital", 0)),
            provider_ref_id=str(payload.get("providerRefId", payload.get("id"))),
            latest_pnl=float(payload["latestPnl"]) if isinstance(payload.get("latestPnl"), (int, float)) else None,
            created_at=str(payload.get("createdAt", utc_now())),
            updated_at=str(payload.get("updatedAt", utc_now())),
        )

    @staticmethod
    def _to_order_record(payload: dict[str, Any]) -> OrderRecord:
        return OrderRecord(
            id=str(payload.get("id")),
            symbol=str(payload.get("symbol")),
            side=str(payload.get("side")),
            order_type=str(payload.get("type", "market")),
            quantity=float(payload.get("quantity", 0)),
            price=float(payload["price"]) if isinstance(payload.get("price"), (int, float)) else None,
            status=str(payload.get("status", "failed")),
            deployment_id=str(payload["deploymentId"]) if payload.get("deploymentId") is not None else None,
            provider_order_id=str(payload.get("providerOrderId", payload.get("id"))),
            created_at=str(payload.get("createdAt", utc_now())),
        )

    @staticmethod
    def _to_portfolio_record(payload: dict[str, Any]) -> PortfolioRecord:
        positions_payload = payload.get("positions")
        positions: list[PositionRecord] = []
        if isinstance(positions_payload, list):
            for entry in positions_payload:
                if not isinstance(entry, dict):
                    continue
                positions.append(
                    PositionRecord(
                        symbol=str(entry.get("symbol", "")),
                        quantity=float(entry.get("quantity", 0)),
                        avg_price=float(entry.get("avgPrice", 0)),
                        current_price=float(entry.get("currentPrice", 0)),
                        unrealized_pnl=float(entry.get("unrealizedPnl", 0)),
                    )
                )
        return PortfolioRecord(
            id=str(payload.get("id")),
            mode=str(payload.get("mode", "paper")),
            cash=float(payload.get("cash", 0)),
            total_value=float(payload.get("totalValue", 0)),
            pnl_total=float(payload["pnlTotal"]) if isinstance(payload.get("pnlTotal"), (int, float)) else None,
            positions=positions,
        )


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
