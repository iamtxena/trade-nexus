"""Services backing the additive /v2 KB/Data endpoints."""

from __future__ import annotations

from src.platform_api.adapters.data_knowledge_adapter import DataKnowledgeAdapter
from src.platform_api.errors import PlatformAPIError
from src.platform_api.knowledge.models import KnowledgePatternRecord, MarketRegimeRecord
from src.platform_api.knowledge.query import KnowledgeQueryService
from src.platform_api.schemas_v1 import MarketScanRequest, RequestContext
from src.platform_api.schemas_v2 import (
    BacktestDataExport,
    BacktestDataExportRequest,
    BacktestDataExportResponse,
    KnowledgePattern,
    KnowledgePatternListResponse,
    KnowledgeRegime,
    KnowledgeRegimeResponse,
    KnowledgeSearchItem,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    MarketScanV2Response,
)
from src.platform_api.services.strategy_backtest_service import StrategyBacktestService


class KnowledgeV2Service:
    def __init__(self, query_service: KnowledgeQueryService) -> None:
        self._query_service = query_service

    async def search(self, *, request: KnowledgeSearchRequest, context: RequestContext) -> KnowledgeSearchResponse:
        items = self._query_service.search(query=request.query, assets=request.assets, limit=request.limit)
        return KnowledgeSearchResponse(
            requestId=context.request_id,
            items=[KnowledgeSearchItem(**item) for item in items],
        )

    async def list_patterns(
        self,
        *,
        pattern_type: str | None,
        asset: str | None,
        limit: int,
        context: RequestContext,
    ) -> KnowledgePatternListResponse:
        items = self._query_service.list_patterns(pattern_type=pattern_type, asset=asset, limit=limit)
        return KnowledgePatternListResponse(
            requestId=context.request_id,
            items=[self._to_pattern(item) for item in items],
        )

    async def get_regime(self, *, asset: str, context: RequestContext) -> KnowledgeRegimeResponse:
        regime = self._query_service.get_regime(asset=asset)
        if regime is None:
            raise PlatformAPIError(
                status_code=404,
                code="KNOWLEDGE_REGIME_NOT_FOUND",
                message=f"No active regime found for {asset}.",
                request_id=context.request_id,
            )
        return KnowledgeRegimeResponse(requestId=context.request_id, regime=self._to_regime(regime))

    @staticmethod
    def _to_pattern(record: KnowledgePatternRecord) -> KnowledgePattern:
        return KnowledgePattern(
            id=record.id,
            name=record.name,
            type=record.pattern_type,
            description=record.description,
            suitableRegimes=record.suitable_regimes,
            assets=record.assets,
            timeframes=record.timeframes,
            confidenceScore=record.confidence_score,
            sourceRef=record.source_ref,
            schemaVersion=record.schema_version,
            createdAt=record.created_at,
            updatedAt=record.updated_at,
        )

    @staticmethod
    def _to_regime(record: MarketRegimeRecord) -> KnowledgeRegime:
        return KnowledgeRegime(
            id=record.id,
            asset=record.asset,
            regime=record.regime,
            volatility=record.volatility,
            indicators=record.indicators,
            startAt=record.start_at,
            endAt=record.end_at,
            notes=record.notes,
            schemaVersion=record.schema_version,
            createdAt=record.created_at,
        )


class DataV2Service:
    def __init__(self, data_adapter: DataKnowledgeAdapter) -> None:
        self._data_adapter = data_adapter

    async def create_backtest_export(
        self,
        *,
        request: BacktestDataExportRequest,
        context: RequestContext,
    ) -> BacktestDataExportResponse:
        payload = await self._data_adapter.create_backtest_export(
            dataset_ids=request.datasetIds,
            asset_classes=request.assetClasses,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            request_id=context.request_id,
        )
        return BacktestDataExportResponse(
            requestId=context.request_id,
            export=BacktestDataExport(**payload),
        )

    async def get_backtest_export(self, *, export_id: str, context: RequestContext) -> BacktestDataExportResponse:
        payload = await self._data_adapter.get_backtest_export(
            export_id=export_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            request_id=context.request_id,
        )
        if payload is None:
            raise PlatformAPIError(
                status_code=404,
                code="DATA_EXPORT_NOT_FOUND",
                message=f"Backtest export {export_id} not found.",
                request_id=context.request_id,
            )
        return BacktestDataExportResponse(requestId=context.request_id, export=BacktestDataExport(**payload))


class ResearchV2Service:
    def __init__(
        self,
        *,
        strategy_service: StrategyBacktestService,
        query_service: KnowledgeQueryService,
        data_adapter: DataKnowledgeAdapter,
    ) -> None:
        self._strategy_service = strategy_service
        self._query_service = query_service
        self._data_adapter = data_adapter

    async def market_scan(self, *, request: MarketScanRequest, context: RequestContext) -> MarketScanV2Response:
        base = await self._strategy_service.market_scan(request=request, context=context)
        evidence = self._query_service.search(
            query=" ".join(request.assetClasses) if request.assetClasses else "market",
            assets=request.assetClasses,
            limit=5,
        )
        context_payload = await self._data_adapter.get_market_context(
            asset_classes=request.assetClasses,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            request_id=context.request_id,
        )
        summary = str(context_payload.get("regimeSummary", "Context unavailable."))
        return MarketScanV2Response(
            requestId=context.request_id,
            regimeSummary=base.regimeSummary,
            strategyIdeas=base.strategyIdeas,
            knowledgeEvidence=[KnowledgeSearchItem(**item) for item in evidence],
            dataContextSummary=summary,
        )
