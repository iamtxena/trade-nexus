"""Deployment, portfolio, and order orchestration through execution adapter boundary."""

from __future__ import annotations

import logging
from time import monotonic
from typing import Literal

from src.platform_api.adapters.execution_adapter import (
    ExecutionAdapter,
    deployment_to_dict,
    order_to_dict,
    portfolio_to_dict,
)
from src.platform_api.errors import PlatformAPIError
from src.platform_api.knowledge.ingestion import KnowledgeIngestionPipeline
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
from src.platform_api.services.execution_lifecycle_mapping import apply_deployment_transition, apply_order_transition
from src.platform_api.services.risk_killswitch_service import RiskKillSwitchService
from src.platform_api.services.reconciliation_service import ReconciliationService
from src.platform_api.services.risk_pretrade_service import RiskPreTradeService
from src.platform_api.state_store import DeploymentRecord, InMemoryStateStore, OrderRecord, utc_now

ReconciliationScope = Literal["deployments", "orders"]
logger = logging.getLogger(__name__)


class ExecutionService:
    """Platform service for execution and portfolio endpoints."""

    def __init__(
        self,
        *,
        store: InMemoryStateStore,
        execution_adapter: ExecutionAdapter,
        reconciliation_service: ReconciliationService | None = None,
        knowledge_ingestion_pipeline: KnowledgeIngestionPipeline | None = None,
        reconciliation_min_interval_seconds: float = 5.0,
    ) -> None:
        self._store = store
        self._execution_adapter = execution_adapter
        self._reconciliation_service = reconciliation_service
        self._knowledge_ingestion_pipeline = knowledge_ingestion_pipeline
        self._reconciliation_min_interval_seconds = max(0.0, reconciliation_min_interval_seconds)
        self._last_reconciliation_run_by_scope: dict[ReconciliationScope, float] = {
            "deployments": 0.0,
            "orders": 0.0,
        }
        self._risk_pretrade_service = RiskPreTradeService(store=store)
        self._risk_killswitch_service = RiskKillSwitchService(store=store)

    async def list_deployments(
        self,
        *,
        status: str | None,
        cursor: str | None,
        context: RequestContext,
    ) -> DeploymentListResponse:
        await self._run_drift_checks(context=context, scope="deployments")
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

        self._risk_pretrade_service.ensure_deployment_allowed(request=request, context=context)
        provider_result = await self._execution_adapter.create_deployment(
            strategy_id=request.strategyId,
            mode=request.mode,
            capital=request.capital,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            idempotency_key=idempotency_key,
        )

        deployment_id = str(provider_result["deploymentId"])
        record = self._store.deployments.get(deployment_id)
        if record is None:
            record = DeploymentRecord(
                id=deployment_id,
                strategy_id=request.strategyId,
                mode=request.mode,
                status=apply_deployment_transition("queued", str(provider_result.get("status", "queued"))),
                capital=request.capital,
                provider_ref_id=str(provider_result.get("providerDeploymentId", deployment_id)),
                latest_pnl=None,
            )
            self._store.deployments[deployment_id] = record
        else:
            record.status = apply_deployment_transition(record.status, str(provider_result.get("status", record.status)))
            record.updated_at = utc_now()
        deployment_dict = deployment_to_dict(record)
        self._store.save_idempotent_response(
            scope="deployments",
            key=idempotency_key,
            payload=payload,
            response=deployment_dict,
        )

        if self._knowledge_ingestion_pipeline is not None:
            self._knowledge_ingestion_pipeline.ingest_deployment_outcome(record)

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
        if record.provider_ref_id:
            provider_state = await self._execution_adapter.get_deployment(
                provider_deployment_id=record.provider_ref_id,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            )
            previous_status = record.status
            record.status = apply_deployment_transition(record.status, str(provider_state.get("status", record.status)))
            latest_pnl = provider_state.get("latestPnl")
            if isinstance(latest_pnl, (int, float)):
                record.latest_pnl = float(latest_pnl)
            kill_switch_triggered = self._risk_killswitch_service.evaluate_drawdown_breach(
                deployment_id=record.id,
                capital=record.capital,
                latest_pnl=record.latest_pnl,
                context=context,
            )
            if kill_switch_triggered and record.status not in {"stopping", "stopped", "failed"}:
                stop_result = await self._execution_adapter.stop_deployment(
                    provider_deployment_id=record.provider_ref_id,
                    reason=(
                        self._risk_killswitch_service.kill_switch_reason()
                        or "Risk kill-switch drawdown breach."
                    ),
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                )
                record.status = apply_deployment_transition(
                    record.status,
                    str(stop_result.get("status", "stopping")),
                )
            if record.status != previous_status:
                record.updated_at = utc_now()
                if self._knowledge_ingestion_pipeline is not None:
                    self._knowledge_ingestion_pipeline.ingest_deployment_outcome(record)
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

        previous_status = record.status
        provider_status = str(stop_result.get("status", "failed"))
        record.status = apply_deployment_transition(previous_status, provider_status)
        record.updated_at = utc_now()
        if self._knowledge_ingestion_pipeline is not None:
            self._knowledge_ingestion_pipeline.ingest_deployment_outcome(record)
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
        await self._run_drift_checks(context=context, scope="orders")
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

        self._risk_pretrade_service.ensure_order_allowed(request=request, context=context)
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
        record = self._store.orders.get(order_id)
        if record is None:
            record = OrderRecord(
                id=order_id,
                symbol=request.symbol,
                side=request.side,
                order_type=request.type,
                quantity=request.quantity,
                price=request.price,
                status=apply_order_transition("pending", str(provider_result.get("status", "pending"))),
                deployment_id=request.deploymentId,
                provider_order_id=str(provider_result.get("providerOrderId", order_id)),
            )
            self._store.orders[order_id] = record
        else:
            record.status = apply_order_transition(record.status, str(provider_result.get("status", record.status)))
            record.provider_order_id = record.provider_order_id or str(provider_result.get("providerOrderId", order_id))
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
        if record.provider_order_id:
            provider_record = await self._execution_adapter.get_order(
                provider_order_id=record.provider_order_id,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            )
            if provider_record is not None:
                record.status = apply_order_transition(record.status, provider_record.status)
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

        record.status = apply_order_transition(record.status, str(result.get("status", "cancelled")))
        return OrderResponse(requestId=context.request_id, order=Order(**order_to_dict(record)))

    async def _run_drift_checks(self, *, context: RequestContext, scope: ReconciliationScope) -> None:
        if self._reconciliation_service is None:
            return

        now = monotonic()
        if self._reconciliation_min_interval_seconds > 0:
            last_run = self._last_reconciliation_run_by_scope[scope]
            if last_run > 0 and (now - last_run) < self._reconciliation_min_interval_seconds:
                return
        self._last_reconciliation_run_by_scope[scope] = now

        try:
            if scope == "deployments":
                await self._reconciliation_service.run_deployment_drift_checks(
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                    request_id=context.request_id,
                )
            else:
                await self._reconciliation_service.run_order_drift_checks(
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                    request_id=context.request_id,
                )
        except Exception:
            logger.exception(
                "Reconciliation drift check failed; continuing list request.",
                extra={"scope": scope, "request_id": context.request_id},
            )
            return
