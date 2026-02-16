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
    CreateConversationSessionRequest,
    CreateConversationTurnRequest,
    KnowledgePatternListResponse,
    KnowledgeRegimeResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    MarketScanV2Response,
)
from src.platform_api.services.conversation_service import ConversationService
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


async def _request_context(
    request: Request,
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
) -> RequestContext:
    request_id = x_request_id or f"req-{uuid4()}"
    request.state.request_id = request_id
    return RequestContext(
        request_id=request_id,
        tenant_id=request.headers.get("X-Tenant-Id", "tenant-local"),
        user_id=request.headers.get("X-User-Id", "user-local"),
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
