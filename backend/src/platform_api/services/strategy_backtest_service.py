"""Strategy, research, and backtest orchestration via adapter boundaries."""

from __future__ import annotations

import asyncio
import math
import threading
from dataclasses import dataclass

from src.platform_api.adapters.lona_adapter import AdapterError, LonaAdapter
from src.platform_api.errors import PlatformAPIError
from src.platform_api.knowledge.ingestion import KnowledgeIngestionPipeline
from src.platform_api.schemas_v1 import (
    Backtest,
    BacktestMetrics,
    CreateBacktestRequest,
    CreateStrategyRequest,
    MarketScanIdea,
    MarketScanRequest,
    MarketScanResponse,
    RequestContext,
    Strategy,
    StrategyListResponse,
    StrategyResponse,
    UpdateStrategyRequest,
)
from src.platform_api.services.backtest_resolution_service import BacktestResolutionService
from src.platform_api.state_store import BacktestRecord, InMemoryStateStore, StrategyRecord, utc_now


@dataclass(frozen=True)
class MarketScanBudgetReservation:
    cost_usd: float
    spent_before_usd: float
    spent_after_usd: float
    max_total_usd: float
    max_per_request_usd: float


class StrategyBacktestService:
    """Platform-facing service for research, strategy, and backtest flows."""

    def __init__(
        self,
        *,
        store: InMemoryStateStore,
        lona_adapter: LonaAdapter,
        backtest_resolution_service: BacktestResolutionService,
        knowledge_ingestion_pipeline: KnowledgeIngestionPipeline | None = None,
    ) -> None:
        self._store = store
        self._lona_adapter = lona_adapter
        self._backtest_resolution_service = backtest_resolution_service
        self._knowledge_ingestion_pipeline = knowledge_ingestion_pipeline
        self._research_budget_lock = threading.Lock()

    async def market_scan(self, *, request: MarketScanRequest, context: RequestContext) -> MarketScanResponse:
        symbol_snapshot: list[str] = []
        fallback_note: str | None = None
        reservation = await self._reserve_market_scan_budget(context=context)
        try:
            provider_symbols = await self._lona_adapter.list_symbols(
                is_global=False,
                limit=max(1, len(request.assetClasses)),
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            )
            symbol_snapshot = [
                str(entry.get("name", "")).upper()
                for entry in provider_symbols
                if isinstance(entry, dict) and entry.get("name")
            ]
            if len(symbol_snapshot) == 0:
                fallback_note = "Lona symbol snapshot was empty; using deterministic fallback symbols."
        except AdapterError as exc:
            await self._release_market_scan_budget(
                reservation=reservation,
                context=context,
                reason=f"adapter_error:{exc.code}",
            )
            fallback_note = f"Lona symbol snapshot unavailable ({exc.code}); using deterministic fallback symbols."
        except asyncio.CancelledError:
            await self._release_market_scan_budget(
                reservation=reservation,
                context=context,
                reason="adapter_error_unexpected:CancelledError",
            )
            raise
        except Exception as exc:
            await self._release_market_scan_budget(
                reservation=reservation,
                context=context,
                reason=f"adapter_error_unexpected:{type(exc).__name__}",
            )
            fallback_note = (
                "Lona symbol snapshot unavailable (adapter_unexpected_error); "
                "using deterministic fallback symbols."
            )

        ideas = [
            MarketScanIdea(
                name=f"{asset.upper()} Momentum Scout",
                assetClass=asset,
                description=f"{asset.upper()} trend and volatility baseline scan.",
                rationale=(
                    "Thin-slice research baseline signal from platform heuristics. "
                    f"Symbol anchor: {(symbol_snapshot[idx % len(symbol_snapshot)] if symbol_snapshot else f'{asset.upper()}USDT')}."
                    + (f" {fallback_note}" if fallback_note else "")
                ),
            )
            for idx, asset in enumerate(request.assetClasses)
        ]
        regime = "Risk-on momentum with elevated volatility clusters."
        if symbol_snapshot:
            regime = f"{regime} Lona symbol snapshot: {', '.join(symbol_snapshot[:3])}."
        elif fallback_note:
            regime = f"{regime} {fallback_note}"
        return MarketScanResponse(requestId=context.request_id, regimeSummary=regime, strategyIdeas=ideas)

    async def _reserve_market_scan_budget(self, *, context: RequestContext) -> MarketScanBudgetReservation:
        with self._research_budget_lock:
            policy = self._store.research_provider_budget
            if not isinstance(policy, dict):
                raise PlatformAPIError(
                    status_code=500,
                    code="RESEARCH_PROVIDER_BUDGET_INVALID",
                    message="Research provider budget policy is invalid.",
                    request_id=context.request_id,
                )

            max_total = self._read_budget_value(policy=policy, key="maxTotalCostUsd", context=context)
            max_per_request = self._read_budget_value(policy=policy, key="maxPerRequestCostUsd", context=context)
            estimated_cost = self._read_budget_value(policy=policy, key="estimatedMarketScanCostUsd", context=context)
            spent_before = self._read_budget_value(policy=policy, key="spentCostUsd", context=context)

            if estimated_cost > max_per_request:
                self._record_research_budget_event(
                    context=context,
                    decision="blocked",
                    reason="per_request_limit_breached",
                    cost_usd=estimated_cost,
                    spent_before_usd=spent_before,
                    spent_after_usd=spent_before,
                    max_total_usd=max_total,
                    max_per_request_usd=max_per_request,
                )
                raise PlatformAPIError(
                    status_code=429,
                    code="RESEARCH_PROVIDER_BUDGET_EXCEEDED",
                    message=(
                        "Research provider budget exceeded: "
                        f"estimated market-scan cost {estimated_cost} exceeds maxPerRequestCostUsd {max_per_request}."
                    ),
                    request_id=context.request_id,
                )

            spent_after = spent_before + estimated_cost
            if spent_after > max_total:
                self._record_research_budget_event(
                    context=context,
                    decision="blocked",
                    reason="total_budget_exceeded",
                    cost_usd=estimated_cost,
                    spent_before_usd=spent_before,
                    spent_after_usd=spent_after,
                    max_total_usd=max_total,
                    max_per_request_usd=max_per_request,
                )
                raise PlatformAPIError(
                    status_code=429,
                    code="RESEARCH_PROVIDER_BUDGET_EXCEEDED",
                    message=(
                        "Research provider budget exceeded: "
                        f"projected spend {spent_after} exceeds maxTotalCostUsd {max_total}."
                    ),
                    request_id=context.request_id,
                )

            policy["spentCostUsd"] = spent_after
            self._record_research_budget_event(
                context=context,
                decision="reserved",
                reason="within_budget",
                cost_usd=estimated_cost,
                spent_before_usd=spent_before,
                spent_after_usd=spent_after,
                max_total_usd=max_total,
                max_per_request_usd=max_per_request,
            )
            return MarketScanBudgetReservation(
                cost_usd=estimated_cost,
                spent_before_usd=spent_before,
                spent_after_usd=spent_after,
                max_total_usd=max_total,
                max_per_request_usd=max_per_request,
            )

    async def _release_market_scan_budget(
        self,
        *,
        reservation: MarketScanBudgetReservation,
        context: RequestContext,
        reason: str,
    ) -> None:
        with self._research_budget_lock:
            policy = self._store.research_provider_budget
            if not isinstance(policy, dict):
                return

            raw_spent = policy.get("spentCostUsd")
            if isinstance(raw_spent, bool) or not isinstance(raw_spent, (int, float)):
                return
            spent_before = float(raw_spent)
            if not math.isfinite(spent_before):
                return

            spent_after = max(0.0, spent_before - reservation.cost_usd)
            policy["spentCostUsd"] = spent_after
            self._record_research_budget_event(
                context=context,
                decision="released",
                reason=reason,
                cost_usd=reservation.cost_usd,
                spent_before_usd=spent_before,
                spent_after_usd=spent_after,
                max_total_usd=reservation.max_total_usd,
                max_per_request_usd=reservation.max_per_request_usd,
            )

    def _read_budget_value(
        self,
        *,
        policy: dict[str, object],
        key: str,
        context: RequestContext,
    ) -> float:
        if key not in policy:
            raise PlatformAPIError(
                status_code=500,
                code="RESEARCH_PROVIDER_BUDGET_INVALID",
                message=f"Research provider budget field {key} is required.",
                request_id=context.request_id,
            )

        raw = policy[key]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise PlatformAPIError(
                status_code=500,
                code="RESEARCH_PROVIDER_BUDGET_INVALID",
                message=f"Research provider budget field {key} must be a finite non-negative number.",
                request_id=context.request_id,
            )

        value = float(raw)
        if not math.isfinite(value) or value < 0.0:
            raise PlatformAPIError(
                status_code=500,
                code="RESEARCH_PROVIDER_BUDGET_INVALID",
                message=f"Research provider budget field {key} must be a finite non-negative number.",
                request_id=context.request_id,
            )
        return value

    def _record_research_budget_event(
        self,
        *,
        context: RequestContext,
        decision: str,
        reason: str,
        cost_usd: float,
        spent_before_usd: float,
        spent_after_usd: float,
        max_total_usd: float,
        max_per_request_usd: float,
    ) -> None:
        if not isinstance(self._store.research_budget_events, list):
            self._store.research_budget_events = []
        self._store.research_budget_events.append(
            {
                "timestamp": utc_now(),
                "requestId": context.request_id,
                "tenantId": context.tenant_id,
                "userId": context.user_id,
                "operation": "market_scan:list_symbols",
                "decision": decision,
                "reason": reason,
                "costUsd": cost_usd,
                "spentBeforeUsd": spent_before_usd,
                "spentAfterUsd": spent_after_usd,
                "maxTotalCostUsd": max_total_usd,
                "maxPerRequestCostUsd": max_per_request_usd,
            }
        )

    async def list_strategies(
        self,
        *,
        status: str | None,
        cursor: str | None,
        context: RequestContext,
    ) -> StrategyListResponse:
        items = list(self._store.strategies.values())
        if status:
            items = [item for item in items if item.status == status]
        strategies = [self._to_strategy(item) for item in items]
        return StrategyListResponse(requestId=context.request_id, items=strategies, nextCursor=None)

    async def create_strategy(self, *, request: CreateStrategyRequest, context: RequestContext) -> StrategyResponse:
        try:
            provider_result = await self._lona_adapter.create_strategy_from_description(
                name=request.name,
                description=request.description,
                provider=request.provider,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            )
        except AdapterError as exc:
            raise PlatformAPIError(
                status_code=exc.status_code,
                code=exc.code,
                message=str(exc),
                request_id=context.request_id,
            )

        strategy_id = self._store.next_id("strategy")
        now = utc_now()
        record = StrategyRecord(
            id=strategy_id,
            name=str(provider_result.get("name") or request.name or "Generated Strategy"),
            description=request.description,
            status="draft",
            provider="lona",
            provider_ref_id=str(provider_result.get("providerRefId") or f"lona-{strategy_id}"),
            tags=[],
            created_at=now,
            updated_at=now,
        )
        self._store.strategies[strategy_id] = record
        return StrategyResponse(requestId=context.request_id, strategy=self._to_strategy(record))

    async def get_strategy(self, *, strategy_id: str, context: RequestContext) -> StrategyResponse:
        record = self._store.strategies.get(strategy_id)
        if record is None:
            raise PlatformAPIError(
                status_code=404,
                code="STRATEGY_NOT_FOUND",
                message=f"Strategy {strategy_id} not found.",
                request_id=context.request_id,
            )
        return StrategyResponse(requestId=context.request_id, strategy=self._to_strategy(record))

    async def update_strategy(
        self,
        *,
        strategy_id: str,
        request: UpdateStrategyRequest,
        context: RequestContext,
    ) -> StrategyResponse:
        record = self._store.strategies.get(strategy_id)
        if record is None:
            raise PlatformAPIError(
                status_code=404,
                code="STRATEGY_NOT_FOUND",
                message=f"Strategy {strategy_id} not found.",
                request_id=context.request_id,
            )

        if request.name is not None:
            record.name = request.name
        if request.description is not None:
            record.description = request.description
        if request.status is not None:
            record.status = request.status
        if request.tags is not None:
            record.tags = request.tags
        record.updated_at = utc_now()

        return StrategyResponse(requestId=context.request_id, strategy=self._to_strategy(record))

    async def create_backtest(
        self,
        *,
        strategy_id: str,
        request: CreateBacktestRequest,
        context: RequestContext,
    ) -> Backtest:
        strategy = self._store.strategies.get(strategy_id)
        if strategy is None:
            raise PlatformAPIError(
                status_code=404,
                code="STRATEGY_NOT_FOUND",
                message=f"Strategy {strategy_id} not found.",
                request_id=context.request_id,
            )

        if request.datasetIds:
            data_ids = await self._backtest_resolution_service.resolve_data_ids(
                dataset_ids=request.datasetIds,
                context=context,
            )
        else:
            data_ids = request.dataIds or []

        try:
            provider_result = await self._lona_adapter.run_backtest(
                provider_ref_id=strategy.provider_ref_id,
                data_ids=data_ids,
                start_date=request.startDate,
                end_date=request.endDate,
                initial_cash=request.initialCash,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            )
        except AdapterError as exc:
            raise PlatformAPIError(
                status_code=exc.status_code,
                code=exc.code,
                message=str(exc),
                request_id=context.request_id,
            )

        backtest_id = self._store.next_id("backtest")
        record = BacktestRecord(
            id=backtest_id,
            strategy_id=strategy_id,
            status="queued",
            created_at=utc_now(),
            provider_report_id=str(provider_result.get("providerReportId")),
        )
        self._store.backtests[backtest_id] = record
        return self._to_backtest(record)

    async def get_backtest(self, *, backtest_id: str, context: RequestContext) -> Backtest:
        record = self._store.backtests.get(backtest_id)
        if record is None:
            raise PlatformAPIError(
                status_code=404,
                code="BACKTEST_NOT_FOUND",
                message=f"Backtest {backtest_id} not found.",
                request_id=context.request_id,
            )

        if record.provider_report_id:
            try:
                provider_report = await self._lona_adapter.get_backtest_report(
                    provider_report_id=record.provider_report_id,
                    tenant_id=context.tenant_id,
                    user_id=context.user_id,
                )
            except AdapterError as exc:
                raise PlatformAPIError(
                    status_code=exc.status_code,
                    code=exc.code,
                    message=str(exc),
                    request_id=context.request_id,
                )

            record.status = provider_report.status
            if provider_report.status == "running" and record.started_at is None:
                record.started_at = utc_now()
            if provider_report.status in {"completed", "failed", "cancelled"} and record.completed_at is None:
                record.completed_at = utc_now()
            if provider_report.metrics is not None:
                record.metrics = provider_report.metrics
            if provider_report.error:
                record.error = provider_report.error

        if self._knowledge_ingestion_pipeline is not None and record.status in {"completed", "failed", "cancelled"}:
            strategy = self._store.strategies.get(record.strategy_id)
            self._knowledge_ingestion_pipeline.ingest_backtest_outcome(strategy=strategy, backtest=record)

        return self._to_backtest(record)

    def _to_strategy(self, record: StrategyRecord) -> Strategy:
        return Strategy(
            id=record.id,
            name=record.name,
            description=record.description,
            status=record.status,
            provider="lona",
            providerRefId=record.provider_ref_id,
            tags=record.tags,
            createdAt=record.created_at,
            updatedAt=record.updated_at,
        )

    def _to_backtest(self, record: BacktestRecord) -> Backtest:
        return Backtest(
            id=record.id,
            strategyId=record.strategy_id,
            status=record.status,
            startedAt=record.started_at,
            completedAt=record.completed_at,
            metrics=BacktestMetrics(**record.metrics),
            error=record.error,
            createdAt=record.created_at,
        )
