"""Deployment, portfolio, and order orchestration through execution adapter boundary."""

from __future__ import annotations

from src.platform_api.adapters.execution_adapter import (
    ExecutionAdapter,
    deployment_to_dict,
    order_to_dict,
    portfolio_to_dict,
)
from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import (
    CreateDeploymentRequest,
    CreateOrderRequest,
    Deployment,
    DeploymentListResponse,
    DeploymentResponse,
    Order,
    OrderListResponse,
    OrderResponse,
    Portfolio,
    PortfolioListResponse,
    PortfolioResponse,
    RequestContext,
)
from src.platform_api.state_store import InMemoryStateStore, utc_now


class ExecutionService:
    """Platform service for execution and portfolio endpoints."""

    def __init__(self, *, store: InMemoryStateStore, execution_adapter: ExecutionAdapter) -> None:
        self._store = store
        self._execution_adapter = execution_adapter

    async def list_deployments(
        self,
        *,
        status: str | None,
        cursor: str | None,
        context: RequestContext,
    ) -> DeploymentListResponse:
        records = await self._execution_adapter.list_deployments(status=status)
        return DeploymentListResponse(
            requestId=context.request_id,
            items=[Deployment(**deployment_to_dict(record)) for record in records],
            nextCursor=None,
        )

    async def create_deployment(
        self,
        *,
        request: CreateDeploymentRequest,
        idempotency_key: str,
        context: RequestContext,
    ) -> DeploymentResponse:
        if request.strategyId not in self._store.strategies:
            raise PlatformAPIError(
                status_code=404,
                code="STRATEGY_NOT_FOUND",
                message=f"Strategy {request.strategyId} not found.",
                request_id=context.request_id,
            )

        payload = request.model_dump()
        conflict, cached = self._store.get_idempotent_response(
            scope="deployments",
            key=idempotency_key,
            payload=payload,
        )
        if conflict:
            raise PlatformAPIError(
                status_code=409,
                code="IDEMPOTENCY_KEY_CONFLICT",
                message="Idempotency-Key reused with different payload.",
                request_id=context.request_id,
            )
        if cached is not None:
            return DeploymentResponse(requestId=context.request_id, deployment=Deployment(**cached))

        provider_result = await self._execution_adapter.create_deployment(
            strategy_id=request.strategyId,
            mode=request.mode,
            capital=request.capital,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            idempotency_key=idempotency_key,
        )

        deployment_id = str(provider_result["deploymentId"])
        record = self._store.deployments[deployment_id]
        deployment_dict = deployment_to_dict(record)
        self._store.save_idempotent_response(
            scope="deployments",
            key=idempotency_key,
            payload=payload,
            response=deployment_dict,
        )

        return DeploymentResponse(requestId=context.request_id, deployment=Deployment(**deployment_dict))

    async def get_deployment(self, *, deployment_id: str, context: RequestContext) -> DeploymentResponse:
        record = self._store.deployments.get(deployment_id)
        if record is None:
            raise PlatformAPIError(
                status_code=404,
                code="DEPLOYMENT_NOT_FOUND",
                message=f"Deployment {deployment_id} not found.",
                request_id=context.request_id,
            )
        return DeploymentResponse(requestId=context.request_id, deployment=Deployment(**deployment_to_dict(record)))

    async def stop_deployment(
        self,
        *,
        deployment_id: str,
        reason: str | None,
        context: RequestContext,
    ) -> DeploymentResponse:
        record = self._store.deployments.get(deployment_id)
        if record is None:
            raise PlatformAPIError(
                status_code=404,
                code="DEPLOYMENT_NOT_FOUND",
                message=f"Deployment {deployment_id} not found.",
                request_id=context.request_id,
            )

        provider_ref = record.provider_ref_id
        if not provider_ref:
            raise PlatformAPIError(
                status_code=404,
                code="DEPLOYMENT_PROVIDER_REF_MISSING",
                message=f"Deployment {deployment_id} provider reference missing.",
                request_id=context.request_id,
            )

        stop_result = await self._execution_adapter.stop_deployment(
            provider_deployment_id=provider_ref,
            reason=reason,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
        )

        provider_status = str(stop_result.get("status", "failed"))
        if provider_status not in {"queued", "running", "paused", "stopping", "stopped", "failed"}:
            provider_status = "failed"
        record.status = provider_status
        record.updated_at = utc_now()
        return DeploymentResponse(requestId=context.request_id, deployment=Deployment(**deployment_to_dict(record)))

    async def list_portfolios(self, *, context: RequestContext) -> PortfolioListResponse:
        records = await self._execution_adapter.list_portfolios()
        return PortfolioListResponse(
            requestId=context.request_id,
            items=[Portfolio(**portfolio_to_dict(record)) for record in records],
        )

    async def get_portfolio(self, *, portfolio_id: str, context: RequestContext) -> PortfolioResponse:
        record = await self._execution_adapter.get_portfolio_snapshot(
            portfolio_id=portfolio_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
        )
        if record is None:
            raise PlatformAPIError(
                status_code=404,
                code="PORTFOLIO_NOT_FOUND",
                message=f"Portfolio {portfolio_id} not found.",
                request_id=context.request_id,
            )

        return PortfolioResponse(requestId=context.request_id, portfolio=Portfolio(**portfolio_to_dict(record)))

    async def list_orders(
        self,
        *,
        status: str | None,
        cursor: str | None,
        context: RequestContext,
    ) -> OrderListResponse:
        records = await self._execution_adapter.list_orders(status=status)
        return OrderListResponse(
            requestId=context.request_id,
            items=[Order(**order_to_dict(record)) for record in records],
            nextCursor=None,
        )

    async def create_order(
        self,
        *,
        request: CreateOrderRequest,
        idempotency_key: str,
        context: RequestContext,
    ) -> OrderResponse:
        payload = request.model_dump()
        conflict, cached = self._store.get_idempotent_response(
            scope="orders",
            key=idempotency_key,
            payload=payload,
        )
        if conflict:
            raise PlatformAPIError(
                status_code=409,
                code="IDEMPOTENCY_KEY_CONFLICT",
                message="Idempotency-Key reused with different payload.",
                request_id=context.request_id,
            )
        if cached is not None:
            return OrderResponse(requestId=context.request_id, order=Order(**cached))

        provider_result = await self._execution_adapter.place_order(
            symbol=request.symbol,
            side=request.side,
            order_type=request.type,
            quantity=request.quantity,
            price=request.price,
            deployment_id=request.deploymentId,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            idempotency_key=idempotency_key,
        )

        order_id = str(provider_result["orderId"])
        record = self._store.orders[order_id]
        order_dict = order_to_dict(record)
        self._store.save_idempotent_response(
            scope="orders",
            key=idempotency_key,
            payload=payload,
            response=order_dict,
        )

        return OrderResponse(requestId=context.request_id, order=Order(**order_dict))

    async def get_order(self, *, order_id: str, context: RequestContext) -> OrderResponse:
        record = self._store.orders.get(order_id)
        if record is None:
            raise PlatformAPIError(
                status_code=404,
                code="ORDER_NOT_FOUND",
                message=f"Order {order_id} not found.",
                request_id=context.request_id,
            )
        return OrderResponse(requestId=context.request_id, order=Order(**order_to_dict(record)))

    async def cancel_order(self, *, order_id: str, context: RequestContext) -> OrderResponse:
        record = self._store.orders.get(order_id)
        if record is None:
            raise PlatformAPIError(
                status_code=404,
                code="ORDER_NOT_FOUND",
                message=f"Order {order_id} not found.",
                request_id=context.request_id,
            )

        provider_ref = record.provider_order_id
        if not provider_ref:
            raise PlatformAPIError(
                status_code=404,
                code="ORDER_PROVIDER_REF_MISSING",
                message=f"Order {order_id} provider reference missing.",
                request_id=context.request_id,
            )

        result = await self._execution_adapter.cancel_order(
            provider_order_id=provider_ref,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
        )
        if result.get("status") == "failed":
            raise PlatformAPIError(
                status_code=404,
                code="ORDER_NOT_FOUND",
                message=f"Order {order_id} not found in execution engine.",
                request_id=context.request_id,
            )

        record.status = "cancelled"
        return OrderResponse(requestId=context.request_id, order=Order(**order_to_dict(record)))
