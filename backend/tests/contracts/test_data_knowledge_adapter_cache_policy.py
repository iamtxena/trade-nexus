"""Contract tests for AG-RES-03 market-context cache freshness policy."""

from __future__ import annotations

import asyncio

from src.platform_api.adapters.data_knowledge_adapter import CachingDataKnowledgeAdapter


class _StubMarketContextAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def create_backtest_export(  # type: ignore[no-untyped-def]
        self,
        *,
        dataset_ids: list[str],
        asset_classes: list[str],
        tenant_id: str,
        user_id: str,
        request_id: str,
    ):
        _ = (dataset_ids, asset_classes, tenant_id, user_id, request_id)
        return {}

    async def get_backtest_export(  # type: ignore[no-untyped-def]
        self,
        *,
        export_id: str,
        tenant_id: str,
        user_id: str,
        request_id: str,
    ):
        _ = (export_id, tenant_id, user_id, request_id)
        return None

    async def get_market_context(  # type: ignore[no-untyped-def]
        self,
        *,
        asset_classes: list[str],
        tenant_id: str,
        user_id: str,
        request_id: str,
    ):
        _ = (asset_classes, tenant_id, user_id, request_id)
        self.calls += 1
        return {
            "regimeSummary": f"call-{self.calls}",
            "signals": [{"name": "focus_assets", "value": ",".join(asset_classes)}],
        }


def test_market_context_cache_hit_within_ttl() -> None:
    async def _run() -> None:
        inner = _StubMarketContextAdapter()
        adapter = CachingDataKnowledgeAdapter(inner_adapter=inner, ttl_seconds=10)

        first = await adapter.get_market_context(
            asset_classes=["crypto"],
            tenant_id="tenant-a",
            user_id="user-a",
            request_id="req-cache-001",
        )
        second = await adapter.get_market_context(
            asset_classes=["crypto"],
            tenant_id="tenant-a",
            user_id="user-a",
            request_id="req-cache-002",
        )

        assert inner.calls == 1
        assert first["regimeSummary"] == "call-1"
        assert second["regimeSummary"] == "call-1"

    asyncio.run(_run())


def test_market_context_cache_expires_after_ttl() -> None:
    async def _run() -> None:
        inner = _StubMarketContextAdapter()
        adapter = CachingDataKnowledgeAdapter(inner_adapter=inner, ttl_seconds=0.01)

        await adapter.get_market_context(
            asset_classes=["crypto"],
            tenant_id="tenant-a",
            user_id="user-a",
            request_id="req-cache-003",
        )
        await asyncio.sleep(0.02)
        refreshed = await adapter.get_market_context(
            asset_classes=["crypto"],
            tenant_id="tenant-a",
            user_id="user-a",
            request_id="req-cache-004",
        )

        assert inner.calls == 2
        assert refreshed["regimeSummary"] == "call-2"

    asyncio.run(_run())


def test_market_context_cache_key_is_asset_order_insensitive() -> None:
    async def _run() -> None:
        inner = _StubMarketContextAdapter()
        adapter = CachingDataKnowledgeAdapter(inner_adapter=inner, ttl_seconds=10)

        await adapter.get_market_context(
            asset_classes=["equity", "crypto"],
            tenant_id="tenant-a",
            user_id="user-a",
            request_id="req-cache-005",
        )
        second = await adapter.get_market_context(
            asset_classes=["crypto", "equity"],
            tenant_id="tenant-a",
            user_id="user-a",
            request_id="req-cache-006",
        )

        assert inner.calls == 1
        assert second["regimeSummary"] == "call-1"

    asyncio.run(_run())


def test_market_context_cache_manual_invalidation_forces_refresh() -> None:
    async def _run() -> None:
        inner = _StubMarketContextAdapter()
        adapter = CachingDataKnowledgeAdapter(inner_adapter=inner, ttl_seconds=10)

        await adapter.get_market_context(
            asset_classes=["crypto"],
            tenant_id="tenant-a",
            user_id="user-a",
            request_id="req-cache-007",
        )
        adapter.invalidate_market_context(
            asset_classes=["crypto"],
            tenant_id="tenant-a",
            user_id="user-a",
        )
        refreshed = await adapter.get_market_context(
            asset_classes=["crypto"],
            tenant_id="tenant-a",
            user_id="user-a",
            request_id="req-cache-008",
        )

        assert inner.calls == 2
        assert refreshed["regimeSummary"] == "call-2"

    asyncio.run(_run())
