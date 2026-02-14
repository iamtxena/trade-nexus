"""FastAPI router implementing the OpenAPI v1 platform surface."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request, status

from src.platform_api.adapters.data_bridge_adapter import InMemoryDataBridgeAdapter
from src.platform_api.adapters.execution_adapter import InMemoryExecutionAdapter
from src.platform_api.adapters.lona_adapter import LonaAdapterBaseline
from src.platform_api.schemas_v1 import (
    BacktestResponse,
    CreateBacktestRequest,
    CreateDeploymentRequest,
    CreateOrderRequest,
    CreateStrategyRequest,
    DatasetListResponse,
    DatasetPublishLonaRequest,
    DatasetQualityReportResponse,
    DatasetResponse,
    DatasetTransformCandlesRequest,
    DatasetUploadCompleteRequest,
    DatasetUploadInitRequest,
    DatasetUploadInitResponse,
    DatasetValidateRequest,
    DeploymentListResponse,
    DeploymentResponse,
    HealthResponse,
    MarketScanRequest,
    MarketScanResponse,
    OrderListResponse,
    OrderResponse,
    PortfolioListResponse,
    PortfolioResponse,
    RequestContext,
    StopDeploymentRequest,
    StrategyListResponse,
    StrategyResponse,
    UpdateStrategyRequest,
)
from src.platform_api.services.backtest_resolution_service import BacktestResolutionService
from src.platform_api.services.dataset_orchestrator import DatasetOrchestrator
from src.platform_api.services.execution_service import ExecutionService
from src.platform_api.services.strategy_backtest_service import StrategyBacktestService
from src.platform_api.state_store import InMemoryStateStore

router = APIRouter(prefix="/v1")

_store = InMemoryStateStore()
_use_remote_lona = os.getenv("PLATFORM_USE_REMOTE_LONA", "false").lower() in {"1", "true", "yes"}
_lona_adapter = LonaAdapterBaseline(use_remote_provider=_use_remote_lona)
_execution_adapter = InMemoryExecutionAdapter(_store)
_data_bridge_adapter = InMemoryDataBridgeAdapter(_store)
_backtest_resolution = BacktestResolutionService(_data_bridge_adapter)
_strategy_service = StrategyBacktestService(
    store=_store,
    lona_adapter=_lona_adapter,
    backtest_resolution_service=_backtest_resolution,
)
_execution_service = ExecutionService(store=_store, execution_adapter=_execution_adapter)
_dataset_service = DatasetOrchestrator(store=_store, data_bridge_adapter=_data_bridge_adapter)


async def _request_context(
    request: Request,
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> RequestContext:
    request_id = x_request_id or f"req-{uuid4()}"
    request.state.request_id = request_id
    return RequestContext(
        request_id=request_id,
        tenant_id="tenant-local",
        user_id="user-local",
    )


ContextDep = Annotated[RequestContext, Depends(_request_context)]


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def get_health_v1(
    context: ContextDep,
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="trade-nexus-platform-api",
        timestamp=datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )


@router.post("/research/market-scan", response_model=MarketScanResponse, tags=["Research"])
async def post_market_scan_v1(
    request: MarketScanRequest,
    context: ContextDep,
) -> MarketScanResponse:
    return await _strategy_service.market_scan(request=request, context=context)


@router.get("/strategies", response_model=StrategyListResponse, tags=["Strategies"])
async def list_strategies_v1(
    context: ContextDep,
    status: str | None = None,
    cursor: str | None = None,
) -> StrategyListResponse:
    return await _strategy_service.list_strategies(status=status, cursor=cursor, context=context)


@router.post(
    "/strategies",
    response_model=StrategyResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Strategies"],
)
async def create_strategy_v1(
    request: CreateStrategyRequest,
    context: ContextDep,
) -> StrategyResponse:
    return await _strategy_service.create_strategy(request=request, context=context)


@router.get("/strategies/{strategyId}", response_model=StrategyResponse, tags=["Strategies"])
async def get_strategy_v1(
    strategyId: str,
    context: ContextDep,
) -> StrategyResponse:
    return await _strategy_service.get_strategy(strategy_id=strategyId, context=context)


@router.patch("/strategies/{strategyId}", response_model=StrategyResponse, tags=["Strategies"])
async def update_strategy_v1(
    strategyId: str,
    request: UpdateStrategyRequest,
    context: ContextDep,
) -> StrategyResponse:
    return await _strategy_service.update_strategy(strategy_id=strategyId, request=request, context=context)


@router.post(
    "/strategies/{strategyId}/backtests",
    response_model=BacktestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Backtests"],
)
async def create_backtest_v1(
    strategyId: str,
    request: CreateBacktestRequest,
    context: ContextDep,
) -> BacktestResponse:
    backtest = await _strategy_service.create_backtest(strategy_id=strategyId, request=request, context=context)
    return BacktestResponse(requestId=context.request_id, backtest=backtest)


@router.get("/backtests/{backtestId}", response_model=BacktestResponse, tags=["Backtests"])
async def get_backtest_v1(
    backtestId: str,
    context: ContextDep,
) -> BacktestResponse:
    backtest = await _strategy_service.get_backtest(backtest_id=backtestId, context=context)
    return BacktestResponse(requestId=context.request_id, backtest=backtest)


@router.get("/deployments", response_model=DeploymentListResponse, tags=["Deployments"])
async def list_deployments_v1(
    context: ContextDep,
    status: str | None = None,
    cursor: str | None = None,
) -> DeploymentListResponse:
    return await _execution_service.list_deployments(status=status, cursor=cursor, context=context)


@router.post(
    "/deployments",
    response_model=DeploymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Deployments"],
)
async def create_deployment_v1(
    context: ContextDep,
    request: CreateDeploymentRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> DeploymentResponse:
    return await _execution_service.create_deployment(
        request=request,
        idempotency_key=idempotency_key,
        context=context,
    )


@router.get("/deployments/{deploymentId}", response_model=DeploymentResponse, tags=["Deployments"])
async def get_deployment_v1(
    deploymentId: str,
    context: ContextDep,
) -> DeploymentResponse:
    return await _execution_service.get_deployment(deployment_id=deploymentId, context=context)


@router.post(
    "/deployments/{deploymentId}/actions/stop",
    response_model=DeploymentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Deployments"],
)
async def stop_deployment_v1(
    context: ContextDep,
    deploymentId: str,
    request: StopDeploymentRequest | None = None,
) -> DeploymentResponse:
    reason = request.reason if request is not None else None
    return await _execution_service.stop_deployment(deployment_id=deploymentId, reason=reason, context=context)


@router.get("/portfolios", response_model=PortfolioListResponse, tags=["Portfolios"])
async def list_portfolios_v1(
    context: ContextDep,
) -> PortfolioListResponse:
    return await _execution_service.list_portfolios(context=context)


@router.get("/portfolios/{portfolioId}", response_model=PortfolioResponse, tags=["Portfolios"])
async def get_portfolio_v1(
    portfolioId: str,
    context: ContextDep,
) -> PortfolioResponse:
    return await _execution_service.get_portfolio(portfolio_id=portfolioId, context=context)


@router.get("/orders", response_model=OrderListResponse, tags=["Orders"])
async def list_orders_v1(
    context: ContextDep,
    status: str | None = None,
    cursor: str | None = None,
) -> OrderListResponse:
    return await _execution_service.list_orders(status=status, cursor=cursor, context=context)


@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Orders"],
)
async def create_order_v1(
    context: ContextDep,
    request: CreateOrderRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> OrderResponse:
    return await _execution_service.create_order(
        request=request,
        idempotency_key=idempotency_key,
        context=context,
    )


@router.get("/orders/{orderId}", response_model=OrderResponse, tags=["Orders"])
async def get_order_v1(
    orderId: str,
    context: ContextDep,
) -> OrderResponse:
    return await _execution_service.get_order(order_id=orderId, context=context)


@router.delete("/orders/{orderId}", response_model=OrderResponse, tags=["Orders"])
async def cancel_order_v1(
    orderId: str,
    context: ContextDep,
) -> OrderResponse:
    return await _execution_service.cancel_order(order_id=orderId, context=context)


@router.post(
    "/datasets/uploads:init",
    response_model=DatasetUploadInitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Datasets"],
)
async def init_dataset_upload_v1(
    request: DatasetUploadInitRequest,
    context: ContextDep,
) -> DatasetUploadInitResponse:
    return await _dataset_service.init_upload(request=request, context=context)


@router.post(
    "/datasets/{datasetId}/uploads:complete",
    response_model=DatasetResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Datasets"],
)
async def complete_dataset_upload_v1(
    datasetId: str,
    context: ContextDep,
    request: DatasetUploadCompleteRequest | None = None,
) -> DatasetResponse:
    return await _dataset_service.complete_upload(dataset_id=datasetId, request=request, context=context)


@router.post(
    "/datasets/{datasetId}/validate",
    response_model=DatasetResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Datasets"],
)
async def validate_dataset_v1(
    datasetId: str,
    context: ContextDep,
    request: DatasetValidateRequest | None = None,
) -> DatasetResponse:
    return await _dataset_service.validate_dataset(dataset_id=datasetId, request=request, context=context)


@router.post(
    "/datasets/{datasetId}/transform/candles",
    response_model=DatasetResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Datasets"],
)
async def transform_dataset_v1(
    datasetId: str,
    request: DatasetTransformCandlesRequest,
    context: ContextDep,
) -> DatasetResponse:
    return await _dataset_service.transform_candles(dataset_id=datasetId, request=request, context=context)


@router.post(
    "/datasets/{datasetId}/publish/lona",
    response_model=DatasetResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Datasets"],
)
async def publish_dataset_lona_v1(
    datasetId: str,
    context: ContextDep,
    request: DatasetPublishLonaRequest | None = None,
) -> DatasetResponse:
    return await _dataset_service.publish_lona(dataset_id=datasetId, request=request, context=context)


@router.get("/datasets", response_model=DatasetListResponse, tags=["Datasets"])
async def list_datasets_v1(
    context: ContextDep,
    cursor: str | None = None,
) -> DatasetListResponse:
    return await _dataset_service.list_datasets(cursor=cursor, context=context)


@router.get("/datasets/{datasetId}", response_model=DatasetResponse, tags=["Datasets"])
async def get_dataset_v1(
    datasetId: str,
    context: ContextDep,
) -> DatasetResponse:
    return await _dataset_service.get_dataset(dataset_id=datasetId, context=context)


@router.get(
    "/datasets/{datasetId}/quality-report",
    response_model=DatasetQualityReportResponse,
    tags=["Datasets"],
)
async def get_dataset_quality_report_v1(
    datasetId: str,
    context: ContextDep,
) -> DatasetQualityReportResponse:
    return await _dataset_service.get_quality_report(dataset_id=datasetId, context=context)
