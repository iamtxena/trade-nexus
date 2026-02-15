"""Boundary tests for the Lona adapter baseline contract."""

from __future__ import annotations

import asyncio

from src.platform_api.adapters.data_bridge_adapter import InMemoryDataBridgeAdapter
from src.platform_api.adapters.lona_adapter import LonaAdapterBaseline
from src.platform_api.schemas_v1 import MarketScanRequest, RequestContext
from src.platform_api.services.backtest_resolution_service import BacktestResolutionService
from src.platform_api.services.strategy_backtest_service import StrategyBacktestService
from src.platform_api.state_store import InMemoryStateStore


async def _run_lona_adapter_baseline_strategy_and_backtest_contract() -> None:
    adapter = LonaAdapterBaseline(use_remote_provider=False)

    strategy = await adapter.create_strategy_from_description(
        name="Boundary Strategy",
        description="Boundary test strategy description for adapter contract.",
        provider="xai",
        tenant_id="tenant-a",
        user_id="user-a",
    )
    assert strategy["providerRefId"] is not None
    assert strategy["name"] == "Boundary Strategy"

    backtest = await adapter.run_backtest(
        provider_ref_id=str(strategy["providerRefId"]),
        data_ids=["dataset-btc-1h-2025"],
        start_date="2025-01-01",
        end_date="2025-12-31",
        initial_cash=100000,
        tenant_id="tenant-a",
        user_id="user-a",
    )
    assert "providerReportId" in backtest

    report = await adapter.get_backtest_report(
        provider_report_id=str(backtest["providerReportId"]),
        tenant_id="tenant-a",
        user_id="user-a",
    )
    assert report.status in {"queued", "running", "completed", "failed", "cancelled"}


async def _run_lona_adapter_baseline_symbol_and_download_contract() -> None:
    adapter = LonaAdapterBaseline(use_remote_provider=False)

    symbols = await adapter.list_symbols(
        is_global=False,
        limit=2,
        tenant_id="tenant-a",
        user_id="user-a",
    )
    assert len(symbols) >= 1
    assert {"id", "name"}.issubset(symbols[0].keys())

    download = await adapter.download_market_data(
        symbol="BTCUSDT",
        interval="1h",
        start_date="2025-01-01",
        end_date="2025-01-31",
        tenant_id="tenant-a",
        user_id="user-a",
    )
    assert "dataId" in download


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


async def _run_market_scan_through_lona_adapter_boundary_contract() -> None:
    store = InMemoryStateStore()
    data_bridge = InMemoryDataBridgeAdapter(store)
    backtest_resolution = BacktestResolutionService(data_bridge)
    recording_adapter = _RecordingLonaAdapter()
    service = StrategyBacktestService(
        store=store,
        lona_adapter=recording_adapter,
        backtest_resolution_service=backtest_resolution,
    )
    context = RequestContext(request_id="req-lona-boundary-001", tenant_id="tenant-a", user_id="user-a")
    response = await service.market_scan(
        request=MarketScanRequest(assetClasses=["crypto"], capital=10000),
        context=context,
    )

    assert recording_adapter.list_symbols_calls == 1
    assert "Lona symbol snapshot" in response.regimeSummary
    assert "Symbol anchor:" in (response.strategyIdeas[0].rationale or "")


def test_lona_adapter_baseline_strategy_and_backtest_contract() -> None:
    asyncio.run(_run_lona_adapter_baseline_strategy_and_backtest_contract())


def test_lona_adapter_baseline_symbol_and_download_contract() -> None:
    asyncio.run(_run_lona_adapter_baseline_symbol_and_download_contract())


def test_market_scan_uses_lona_adapter_boundary_contract() -> None:
    asyncio.run(_run_market_scan_through_lona_adapter_boundary_contract())
