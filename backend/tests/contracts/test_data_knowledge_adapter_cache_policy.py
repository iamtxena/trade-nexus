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


def test_market_context_normalizes_top_level_sentiment_into_ml_signals() -> None:
    class _SentimentContextAdapter(_StubMarketContextAdapter):
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
                "regimeSummary": "Sentiment-led recovery.",
                "signals": [{"name": "focus_assets", "value": "crypto"}],
                "sentiment": {
                    "score": "68",
                    "confidence": "81",
                    "source": "curated-news",
                    "sourceCount": 12,
                    "lookbackHours": 24,
                },
                "mlSignals": {
                    "prediction": {"direction": "bullish", "confidence": 0.8},
                    "volatility": {"predictedPct": 32.0, "confidence": 0.66},
                    "anomaly": {"isAnomaly": False, "score": 0.04},
                },
            }

    async def _run() -> None:
        inner = _SentimentContextAdapter()
        adapter = CachingDataKnowledgeAdapter(inner_adapter=inner, ttl_seconds=10)
        payload = await adapter.get_market_context(
            asset_classes=["crypto"],
            tenant_id="tenant-a",
            user_id="user-a",
            request_id="req-cache-009",
        )

        sentiment = payload["mlSignals"]["sentiment"]
        assert sentiment["score"] == 68.0
        assert sentiment["confidence"] == 81.0
        assert sentiment["source"] == "curated-news"
        assert sentiment["sourceCount"] == 12
        assert sentiment["lookbackHours"] == 24

        names = {entry["name"] for entry in payload["signals"]}
        assert "sentiment_score" in names
        assert "sentiment_confidence" in names

    asyncio.run(_run())


def test_market_context_invalid_top_level_sentiment_remains_optional_safe() -> None:
    class _InvalidSentimentAdapter(_StubMarketContextAdapter):
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
                "regimeSummary": "Context with malformed sentiment.",
                "signals": [{"name": "focus_assets", "value": "crypto"}],
                "sentiment": {"score": "bad-data", "confidence": "nan"},
                "mlSignals": {
                    "prediction": {"direction": "neutral", "confidence": 0.55},
                    "volatility": {"predictedPct": 45.0, "confidence": 0.62},
                    "anomaly": {"isAnomaly": False, "score": 0.03},
                },
            }

    async def _run() -> None:
        inner = _InvalidSentimentAdapter()
        adapter = CachingDataKnowledgeAdapter(inner_adapter=inner, ttl_seconds=10)
        payload = await adapter.get_market_context(
            asset_classes=["crypto"],
            tenant_id="tenant-a",
            user_id="user-a",
            request_id="req-cache-010",
        )

        assert "sentiment" not in payload["mlSignals"]
        names = {entry["name"] for entry in payload["signals"]}
        assert "sentiment_score" not in names
        assert "sentiment_confidence" not in names

    asyncio.run(_run())


def test_market_context_merges_top_level_sentiment_metadata_with_existing_ml_sentiment() -> None:
    class _DualSourceSentimentAdapter(_StubMarketContextAdapter):
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
                "regimeSummary": "Dual sentiment source payload.",
                "signals": [{"name": "focus_assets", "value": "crypto"}],
                "sentiment": {
                    "score": 68,
                    "confidence": 81,
                    "source": "curated-news",
                    "sourceCount": 12,
                    "lookbackHours": 24,
                },
                "mlSignals": {
                    "prediction": {"direction": "bullish", "confidence": 0.8},
                    "sentiment": {"score": 0.64, "confidence": 0.71},
                    "volatility": {"predictedPct": 33.0, "confidence": 0.66},
                    "anomaly": {"isAnomaly": False, "score": 0.05},
                },
            }

    async def _run() -> None:
        inner = _DualSourceSentimentAdapter()
        adapter = CachingDataKnowledgeAdapter(inner_adapter=inner, ttl_seconds=10)
        payload = await adapter.get_market_context(
            asset_classes=["crypto"],
            tenant_id="tenant-a",
            user_id="user-a",
            request_id="req-cache-011",
        )

        sentiment = payload["mlSignals"]["sentiment"]
        assert sentiment["score"] == 0.64
        assert sentiment["confidence"] == 0.71
        assert sentiment["source"] == "curated-news"
        assert sentiment["sourceCount"] == 12
        assert sentiment["lookbackHours"] == 24
        assert "sentiment" not in payload

    asyncio.run(_run())


def test_market_context_merges_top_level_regime_metadata_with_existing_ml_regime() -> None:
    class _DualSourceRegimeAdapter(_StubMarketContextAdapter):
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
                "regimeSummary": "Dual regime source payload.",
                "signals": [{"name": "focus_assets", "value": "crypto"}],
                "regime": {
                    "label": "risk_off",
                    "confidence": 91,
                    "source": "macro-engine",
                },
                "mlSignals": {
                    "prediction": {"direction": "neutral", "confidence": 0.7},
                    "sentiment": {"score": 0.48, "confidence": 0.65},
                    "volatility": {"predictedPct": 48.0, "confidence": 0.74},
                    "anomaly": {"isAnomaly": False, "score": 0.08},
                    "regime": {"label": "risk_on"},
                },
            }

    async def _run() -> None:
        inner = _DualSourceRegimeAdapter()
        adapter = CachingDataKnowledgeAdapter(inner_adapter=inner, ttl_seconds=10)
        payload = await adapter.get_market_context(
            asset_classes=["crypto"],
            tenant_id="tenant-a",
            user_id="user-a",
            request_id="req-cache-012",
        )

        regime = payload["mlSignals"]["regime"]
        assert regime["label"] == "risk_on"
        assert regime["confidence"] == 91.0
        assert regime["source"] == "macro-engine"
        assert "regime" not in payload

    asyncio.run(_run())
