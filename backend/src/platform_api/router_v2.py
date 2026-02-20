"""FastAPI router for additive Platform API v2 endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request, status

from src.platform_api import router_v1 as router_v1_module
from src.platform_api.schemas_v1 import MarketScanRequest, RequestContext
from src.platform_api.schemas_v2 import (
    BacktestDataExportRequest,
    BacktestDataExportResponse,
    ConversationSessionResponse,
    ConversationTurnResponse,
    CreateValidationBaselineRequest,
    CreateValidationRegressionReplayRequest,
    CreateValidationRenderRequest,
    CreateValidationRunRequest,
    CreateValidationRunReviewRequest,
    CreateConversationSessionRequest,
    CreateConversationTurnRequest,
    KnowledgePatternListResponse,
    KnowledgeRegimeResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    MarketScanV2Response,
    ValidationArtifactResponse,
    ValidationBaselineResponse,
    ValidationRegressionReplayResponse,
    ValidationRenderResponse,
    ValidationRunResponse,
    ValidationRunListResponse,
    ValidationRunReviewResponse,
)
from src.platform_api.services.conversation_service import ConversationService
from src.platform_api.services.validation_v2_service import ValidationV2Service
from src.platform_api.services.v2_services import DataV2Service, KnowledgeV2Service, ResearchV2Service

router = APIRouter(prefix="/v2")

_knowledge_service = KnowledgeV2Service(router_v1_module._knowledge_query_service)
_data_service = DataV2Service(router_v1_module._data_knowledge_adapter)
_research_service = ResearchV2Service(
    strategy_service=router_v1_module._strategy_service,
    query_service=router_v1_module._knowledge_query_service,
    data_adapter=router_v1_module._data_knowledge_adapter,
    store=router_v1_module._store,
)
_conversation_service = ConversationService(store=router_v1_module._store)
_validation_service = ValidationV2Service(store=router_v1_module._store)


async def _request_context(
    request: Request,
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> RequestContext:
    state_request_id = getattr(request.state, "request_id", None)
    request_id = x_request_id or (state_request_id if isinstance(state_request_id, str) and state_request_id.strip() else f"req-{uuid4()}")
    request.state.request_id = request_id
    state_tenant_id = getattr(request.state, "tenant_id", None)
    state_user_id = getattr(request.state, "user_id", None)
    tenant_id = state_tenant_id if isinstance(state_tenant_id, str) and state_tenant_id.strip() else "tenant-local"
    user_id = state_user_id if isinstance(state_user_id, str) and state_user_id.strip() else "user-local"
    request.state.tenant_id = tenant_id
    request.state.user_id = user_id
    return RequestContext(
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )


ContextDep = Annotated[RequestContext, Depends(_request_context)]


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse, tags=["Knowledge"])
async def search_knowledge_v2(
    request: KnowledgeSearchRequest,
    context: ContextDep,
) -> KnowledgeSearchResponse:
    return await _knowledge_service.search(request=request, context=context)


@router.get("/knowledge/patterns", response_model=KnowledgePatternListResponse, tags=["Knowledge"])
async def list_knowledge_patterns_v2(
    context: ContextDep,
    type: str | None = None,
    asset: str | None = None,
    limit: int = 25,
) -> KnowledgePatternListResponse:
    return await _knowledge_service.list_patterns(
        pattern_type=type,
        asset=asset,
        limit=limit,
        context=context,
    )


@router.get("/knowledge/regimes/{asset}", response_model=KnowledgeRegimeResponse, tags=["Knowledge"])
async def get_knowledge_regime_v2(
    asset: str,
    context: ContextDep,
) -> KnowledgeRegimeResponse:
    return await _knowledge_service.get_regime(asset=asset, context=context)


@router.post(
    "/data/exports/backtest",
    response_model=BacktestDataExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Data"],
)
async def create_backtest_data_export_v2(
    request: BacktestDataExportRequest,
    context: ContextDep,
) -> BacktestDataExportResponse:
    return await _data_service.create_backtest_export(request=request, context=context)


@router.get("/data/exports/{exportId}", response_model=BacktestDataExportResponse, tags=["Data"])
async def get_backtest_data_export_v2(
    exportId: str,
    context: ContextDep,
) -> BacktestDataExportResponse:
    return await _data_service.get_backtest_export(export_id=exportId, context=context)


@router.post("/research/market-scan", response_model=MarketScanV2Response, tags=["Research"])
async def post_market_scan_v2(
    request: MarketScanRequest,
    context: ContextDep,
) -> MarketScanV2Response:
    return await _research_service.market_scan(request=request, context=context)


@router.post(
    "/conversations/sessions",
    response_model=ConversationSessionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Conversations"],
)
async def create_conversation_session_v2(
    request: CreateConversationSessionRequest,
    context: ContextDep,
) -> ConversationSessionResponse:
    return await _conversation_service.create_session(request=request, context=context)


@router.get(
    "/conversations/sessions/{sessionId}",
    response_model=ConversationSessionResponse,
    tags=["Conversations"],
)
async def get_conversation_session_v2(
    sessionId: str,
    context: ContextDep,
) -> ConversationSessionResponse:
    return await _conversation_service.get_session(session_id=sessionId, context=context)


@router.post(
    "/conversations/sessions/{sessionId}/turns",
    response_model=ConversationTurnResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Conversations"],
)
async def create_conversation_turn_v2(
    sessionId: str,
    request: CreateConversationTurnRequest,
    context: ContextDep,
) -> ConversationTurnResponse:
    return await _conversation_service.create_turn(session_id=sessionId, request=request, context=context)


@router.get("/validation-runs", response_model=ValidationRunListResponse, tags=["Validation"])
async def list_validation_runs_v2(
    context: ContextDep,
) -> ValidationRunListResponse:
    return await _validation_service.list_validation_runs(context=context)


@router.post(
    "/validation-runs",
    response_model=ValidationRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Validation"],
)
async def create_validation_run_v2(
    request: CreateValidationRunRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationRunResponse:
    return await _validation_service.create_validation_run(
        request=request,
        context=context,
        idempotency_key=idempotency_key,
    )


@router.get("/validation-runs/{runId}", response_model=ValidationRunResponse, tags=["Validation"])
async def get_validation_run_v2(
    runId: str,
    context: ContextDep,
) -> ValidationRunResponse:
    return await _validation_service.get_validation_run(run_id=runId, context=context)


@router.get(
    "/validation-runs/{runId}/artifact",
    response_model=ValidationArtifactResponse,
    tags=["Validation"],
)
async def get_validation_run_artifact_v2(
    runId: str,
    context: ContextDep,
) -> ValidationArtifactResponse:
    return await _validation_service.get_validation_run_artifact(run_id=runId, context=context)


@router.post(
    "/validation-runs/{runId}/review",
    response_model=ValidationRunReviewResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Validation"],
)
async def submit_validation_run_review_v2(
    runId: str,
    request: CreateValidationRunReviewRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationRunReviewResponse:
    return await _validation_service.submit_validation_run_review(
        run_id=runId,
        request=request,
        context=context,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/validation-runs/{runId}/render",
    response_model=ValidationRenderResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Validation"],
)
async def create_validation_run_render_v2(
    runId: str,
    request: CreateValidationRenderRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationRenderResponse:
    return await _validation_service.create_validation_render(
        run_id=runId,
        request=request,
        context=context,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/validation-baselines",
    response_model=ValidationBaselineResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Validation"],
)
async def create_validation_baseline_v2(
    request: CreateValidationBaselineRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationBaselineResponse:
    return await _validation_service.create_validation_baseline(
        request=request,
        context=context,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/validation-regressions/replay",
    response_model=ValidationRegressionReplayResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Validation"],
)
async def replay_validation_regression_v2(
    request: CreateValidationRegressionReplayRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationRegressionReplayResponse:
    return await _validation_service.replay_validation_regression(
        request=request,
        context=context,
        idempotency_key=idempotency_key,
    )
