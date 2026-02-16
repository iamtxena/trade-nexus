"""Contract tests for AG-RES-04 provider budget and cost guardrails."""

from __future__ import annotations

import asyncio

from src.platform_api.adapters.data_bridge_adapter import InMemoryDataBridgeAdapter
from src.platform_api.adapters.lona_adapter import AdapterError, LonaAdapterBaseline
from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import MarketScanRequest, RequestContext
from src.platform_api.services.backtest_resolution_service import BacktestResolutionService
from src.platform_api.services.strategy_backtest_service import StrategyBacktestService
from src.platform_api.state_store import InMemoryStateStore


class _RecordingLonaAdapter(LonaAdapterBaseline):
    def __init__(self) -> None:
        super().__init__(use_remote_provider=False)
        self.list_symbols_calls = 0

    async def list_symbols(
        self,
        *,
        is_global: bool,
        limit: int,
        tenant_id: str,
        user_id: str,
    ) -> list[dict[str, str]]:
        _ = (is_global, limit, tenant_id, user_id)
        self.list_symbols_calls += 1
        return [{"id": "lona-symbol-001", "name": "BTCUSDT"}, {"id": "lona-symbol-002", "name": "ETHUSDT"}]


def _context(request_id: str = "req-research-budget-001") -> RequestContext:
    return RequestContext(request_id=request_id, tenant_id="tenant-a", user_id="user-a")


async def _create_service_and_store() -> tuple[StrategyBacktestService, InMemoryStateStore, _RecordingLonaAdapter]:
    store = InMemoryStateStore()
    data_bridge = InMemoryDataBridgeAdapter(store)
    backtest_resolution = BacktestResolutionService(data_bridge)
    adapter = _RecordingLonaAdapter()
    service = StrategyBacktestService(
        store=store,
        lona_adapter=adapter,
        backtest_resolution_service=backtest_resolution,
    )
    return service, store, adapter


def test_market_scan_reserves_budget_when_within_limits() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.research_provider_budget = {
            "maxTotalCostUsd": 2.0,
            "maxPerRequestCostUsd": 1.0,
            "estimatedMarketScanCostUsd": 0.4,
            "spentCostUsd": 0.0,
        }

        response = await service.market_scan(
            request=MarketScanRequest(assetClasses=["crypto"], capital=25_000),
            context=_context(),
        )

        assert adapter.list_symbols_calls == 1
        assert len(response.strategyIdeas) == 1
        assert store.research_provider_budget["spentCostUsd"] == 0.4
        assert len(store.research_budget_events) >= 1
        event = store.research_budget_events[-1]
        assert event["decision"] == "reserved"
        assert event["reason"] == "within_budget"
        assert event["spentAfterUsd"] == 0.4

    asyncio.run(_run())


def test_market_scan_fails_closed_when_per_request_budget_is_exceeded() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.research_provider_budget = {
            "maxTotalCostUsd": 2.0,
            "maxPerRequestCostUsd": 0.2,
            "estimatedMarketScanCostUsd": 0.3,
            "spentCostUsd": 0.0,
        }

        try:
            await service.market_scan(
                request=MarketScanRequest(assetClasses=["crypto"], capital=25_000),
                context=_context(),
            )
            raise AssertionError("Expected provider budget guardrail to fail closed.")
        except PlatformAPIError as exc:
            assert exc.status_code == 429
            assert exc.code == "RESEARCH_PROVIDER_BUDGET_EXCEEDED"

        assert adapter.list_symbols_calls == 0
        assert store.research_provider_budget["spentCostUsd"] == 0.0
        assert len(store.research_budget_events) >= 1
        event = store.research_budget_events[-1]
        assert event["decision"] == "blocked"
        assert event["reason"] == "per_request_limit_breached"

    asyncio.run(_run())


def test_market_scan_fails_closed_when_total_budget_is_exceeded() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.research_provider_budget = {
            "maxTotalCostUsd": 0.5,
            "maxPerRequestCostUsd": 1.0,
            "estimatedMarketScanCostUsd": 0.3,
            "spentCostUsd": 0.3,
        }

        try:
            await service.market_scan(
                request=MarketScanRequest(assetClasses=["crypto"], capital=25_000),
                context=_context(),
            )
            raise AssertionError("Expected total provider budget guardrail to fail closed.")
        except PlatformAPIError as exc:
            assert exc.status_code == 429
            assert exc.code == "RESEARCH_PROVIDER_BUDGET_EXCEEDED"

        assert adapter.list_symbols_calls == 0
        assert store.research_provider_budget["spentCostUsd"] == 0.3
        assert len(store.research_budget_events) >= 1
        event = store.research_budget_events[-1]
        assert event["decision"] == "blocked"
        assert event["reason"] == "total_budget_exceeded"

    asyncio.run(_run())


def test_market_scan_fails_closed_when_budget_policy_is_invalid() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.research_provider_budget = {
            "maxTotalCostUsd": "invalid",
            "maxPerRequestCostUsd": 1.0,
            "estimatedMarketScanCostUsd": 0.3,
            "spentCostUsd": 0.0,
        }

        try:
            await service.market_scan(
                request=MarketScanRequest(assetClasses=["crypto"], capital=25_000),
                context=_context(),
            )
            raise AssertionError("Expected invalid budget policy to fail closed.")
        except PlatformAPIError as exc:
            assert exc.status_code == 500
            assert exc.code == "RESEARCH_PROVIDER_BUDGET_INVALID"

        assert adapter.list_symbols_calls == 0
        assert store.research_provider_budget["spentCostUsd"] == 0.0

    asyncio.run(_run())


def test_market_scan_fails_closed_when_budget_field_is_missing() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.research_provider_budget = {
            "maxTotalCostUsd": 1.0,
            "estimatedMarketScanCostUsd": 0.3,
            "spentCostUsd": 0.0,
        }

        try:
            await service.market_scan(
                request=MarketScanRequest(assetClasses=["crypto"], capital=25_000),
                context=_context(),
            )
            raise AssertionError("Expected missing budget fields to fail closed.")
        except PlatformAPIError as exc:
            assert exc.status_code == 500
            assert exc.code == "RESEARCH_PROVIDER_BUDGET_INVALID"

        assert adapter.list_symbols_calls == 0

    asyncio.run(_run())


def test_market_scan_releases_budget_on_adapter_failure() -> None:
    class _FailingLonaAdapter(_RecordingLonaAdapter):
        async def list_symbols(
            self,
            *,
            is_global: bool,
            limit: int,
            tenant_id: str,
            user_id: str,
        ) -> list[dict[str, str]]:
            _ = (is_global, limit, tenant_id, user_id)
            self.list_symbols_calls += 1
            raise AdapterError("temporary upstream outage", code="LONA_LIST_SYMBOLS_FAILED", status_code=502)

    async def _run() -> None:
        store = InMemoryStateStore()
        data_bridge = InMemoryDataBridgeAdapter(store)
        backtest_resolution = BacktestResolutionService(data_bridge)
        adapter = _FailingLonaAdapter()
        service = StrategyBacktestService(
            store=store,
            lona_adapter=adapter,
            backtest_resolution_service=backtest_resolution,
        )
        store.research_provider_budget = {
            "maxTotalCostUsd": 2.0,
            "maxPerRequestCostUsd": 1.0,
            "estimatedMarketScanCostUsd": 0.4,
            "spentCostUsd": 0.0,
        }

        response = await service.market_scan(
            request=MarketScanRequest(assetClasses=["crypto"], capital=25_000),
            context=_context(),
        )

        assert adapter.list_symbols_calls == 1
        assert len(response.strategyIdeas) == 1
        assert store.research_provider_budget["spentCostUsd"] == 0.0
        assert len(store.research_budget_events) >= 2
        assert store.research_budget_events[-2]["decision"] == "reserved"
        assert store.research_budget_events[-1]["decision"] == "released"
        assert store.research_budget_events[-1]["reason"] == "adapter_error:LONA_LIST_SYMBOLS_FAILED"

    asyncio.run(_run())


def test_market_scan_budget_guardrail_is_concurrency_safe() -> None:
    async def _run() -> None:
        service, store, adapter = await _create_service_and_store()
        store.research_provider_budget = {
            "maxTotalCostUsd": 0.3,
            "maxPerRequestCostUsd": 1.0,
            "estimatedMarketScanCostUsd": 0.2,
            "spentCostUsd": 0.0,
        }

        async def _scan(request_id: str) -> str:
            try:
                await service.market_scan(
                    request=MarketScanRequest(assetClasses=["crypto"], capital=25_000),
                    context=_context(request_id=request_id),
                )
                return "ok"
            except PlatformAPIError as exc:
                return exc.code

        results = await asyncio.gather(_scan("req-budget-concurrency-1"), _scan("req-budget-concurrency-2"))

        assert sorted(results) == ["RESEARCH_PROVIDER_BUDGET_EXCEEDED", "ok"]
        assert adapter.list_symbols_calls == 1
        assert store.research_provider_budget["spentCostUsd"] == 0.2

    asyncio.run(_run())
