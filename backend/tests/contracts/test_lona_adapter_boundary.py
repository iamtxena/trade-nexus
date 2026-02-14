"""Boundary tests for the Lona adapter baseline contract."""

from __future__ import annotations

import asyncio

from src.platform_api.adapters.lona_adapter import LonaAdapterBaseline


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


def test_lona_adapter_baseline_strategy_and_backtest_contract() -> None:
    asyncio.run(_run_lona_adapter_baseline_strategy_and_backtest_contract())


def test_lona_adapter_baseline_symbol_and_download_contract() -> None:
    asyncio.run(_run_lona_adapter_baseline_symbol_and_download_contract())
