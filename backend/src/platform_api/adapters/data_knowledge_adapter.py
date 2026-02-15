"""Adapter boundary for trader-data internal service integration."""

from __future__ import annotations

import copy
from time import monotonic
from typing import Protocol

import httpx

from src.platform_api.adapters.lona_adapter import AdapterError
from src.platform_api.state_store import DataExportRecord, InMemoryStateStore, utc_now


class DataKnowledgeAdapter(Protocol):
    async def create_backtest_export(
        self,
        *,
        dataset_ids: list[str],
        asset_classes: list[str],
        tenant_id: str,
        user_id: str,
        request_id: str,
    ) -> dict[str, object]:
        ...

    async def get_backtest_export(
        self,
        *,
        export_id: str,
        tenant_id: str,
        user_id: str,
        request_id: str,
    ) -> dict[str, object] | None:
        ...

    async def get_market_context(
        self,
        *,
        asset_classes: list[str],
        tenant_id: str,
        user_id: str,
        request_id: str,
    ) -> dict[str, object]:
        ...


class CachingDataKnowledgeAdapter:
    """Caches market-context responses with deterministic freshness policy."""

    def __init__(
        self,
        *,
        inner_adapter: DataKnowledgeAdapter,
        ttl_seconds: float = 120.0,
        max_entries: int = 256,
    ) -> None:
        self._inner_adapter = inner_adapter
        self._ttl_seconds = max(0.0, ttl_seconds)
        self._max_entries = max(1, max_entries)
        self._market_context_cache: dict[tuple[str, str, tuple[str, ...]], tuple[float, dict[str, object]]] = {}

    async def create_backtest_export(
        self,
        *,
        dataset_ids: list[str],
        asset_classes: list[str],
        tenant_id: str,
        user_id: str,
        request_id: str,
    ) -> dict[str, object]:
        return await self._inner_adapter.create_backtest_export(
            dataset_ids=dataset_ids,
            asset_classes=asset_classes,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
        )

    async def get_backtest_export(
        self,
        *,
        export_id: str,
        tenant_id: str,
        user_id: str,
        request_id: str,
    ) -> dict[str, object] | None:
        return await self._inner_adapter.get_backtest_export(
            export_id=export_id,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
        )

    async def get_market_context(
        self,
        *,
        asset_classes: list[str],
        tenant_id: str,
        user_id: str,
        request_id: str,
    ) -> dict[str, object]:
        if self._ttl_seconds <= 0:
            return await self._inner_adapter.get_market_context(
                asset_classes=asset_classes,
                tenant_id=tenant_id,
                user_id=user_id,
                request_id=request_id,
            )

        cache_key = self._market_context_key(
            asset_classes=asset_classes,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        now = monotonic()
        cached = self._market_context_cache.get(cache_key)
        if cached is not None:
            expires_at, payload = cached
            if now <= expires_at:
                return copy.deepcopy(payload)

        payload = await self._inner_adapter.get_market_context(
            asset_classes=asset_classes,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
        )
        if not isinstance(payload, dict):
            raise AdapterError("Trader-data market context response must be an object.", code="TRADER_DATA_BAD_RESPONSE")

        self._evict_expired(now=now)
        if len(self._market_context_cache) >= self._max_entries:
            # Deterministic eviction: drop entry with the earliest expiration.
            oldest = min(self._market_context_cache.items(), key=lambda item: item[1][0])[0]
            self._market_context_cache.pop(oldest, None)
        self._market_context_cache[cache_key] = (now + self._ttl_seconds, copy.deepcopy(payload))
        return payload

    def invalidate_market_context(
        self,
        *,
        asset_classes: list[str],
        tenant_id: str,
        user_id: str,
    ) -> None:
        cache_key = self._market_context_key(
            asset_classes=asset_classes,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        self._market_context_cache.pop(cache_key, None)

    def clear_market_context_cache(self) -> None:
        self._market_context_cache.clear()

    @staticmethod
    def _market_context_key(
        *,
        asset_classes: list[str],
        tenant_id: str,
        user_id: str,
    ) -> tuple[str, str, tuple[str, ...]]:
        normalized_assets = tuple(sorted(asset.strip().lower() for asset in asset_classes))
        return (tenant_id, user_id, normalized_assets)

    def _evict_expired(self, *, now: float) -> None:
        stale_keys = [key for key, (expires_at, _) in self._market_context_cache.items() if now > expires_at]
        for key in stale_keys:
            self._market_context_cache.pop(key, None)


class InMemoryDataKnowledgeAdapter:
    """Fallback adapter when trader-data internal API is disabled."""

    def __init__(self, store: InMemoryStateStore) -> None:
        self._store = store

    async def create_backtest_export(
        self,
        *,
        dataset_ids: list[str],
        asset_classes: list[str],
        tenant_id: str,
        user_id: str,
        request_id: str,
    ) -> dict[str, object]:
        export_id = self._store.next_id("export")
        record = DataExportRecord(
            id=export_id,
            status="completed",
            dataset_ids=dataset_ids,
            asset_classes=asset_classes,
            provider_export_ref=f"trader-data-{export_id}",
            download_url=f"https://exports.trade-nexus.local/{export_id}.parquet",
            lineage={"datasets": dataset_ids, "generatedBy": "in-memory-adapter"},
        )
        self._store.data_exports[export_id] = record
        return {
            "id": record.id,
            "status": record.status,
            "datasetIds": record.dataset_ids,
            "assetClasses": record.asset_classes,
            "downloadUrl": record.download_url,
            "lineage": record.lineage,
            "createdAt": record.created_at,
            "updatedAt": record.updated_at,
        }

    async def get_backtest_export(
        self,
        *,
        export_id: str,
        tenant_id: str,
        user_id: str,
        request_id: str,
    ) -> dict[str, object] | None:
        record = self._store.data_exports.get(export_id)
        if record is None:
            return None
        return {
            "id": record.id,
            "status": record.status,
            "datasetIds": record.dataset_ids,
            "assetClasses": record.asset_classes,
            "downloadUrl": record.download_url,
            "lineage": record.lineage,
            "createdAt": record.created_at,
            "updatedAt": record.updated_at,
        }

    async def get_market_context(
        self,
        *,
        asset_classes: list[str],
        tenant_id: str,
        user_id: str,
        request_id: str,
    ) -> dict[str, object]:
        classes = [entry.lower() for entry in asset_classes]
        return {
            "regimeSummary": "Range-bound market with selective momentum breakouts.",
            "signals": [
                {"name": "volatility", "value": "medium"},
                {"name": "liquidity", "value": "stable"},
                {"name": "focus_assets", "value": ",".join(classes) if classes else "crypto"},
            ],
            "mlSignals": {
                "prediction": {
                    "direction": "bullish",
                    "confidence": 0.72,
                    "timeframe": "24h",
                },
                "sentiment": {
                    "score": 0.58,
                    "confidence": 0.66,
                },
                "volatility": {
                    "predictedPct": 44.2,
                    "confidence": 0.61,
                },
                "anomaly": {
                    "isAnomaly": False,
                    "score": 0.08,
                },
            },
            "generatedAt": utc_now(),
        }


class TraderDataHTTPAdapter:
    """HTTP implementation against trader-data internal API."""

    def __init__(
        self,
        *,
        base_url: str,
        service_api_key: str,
        timeout_seconds: float = 8.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._service_api_key = service_api_key
        self._timeout_seconds = timeout_seconds

    async def create_backtest_export(
        self,
        *,
        dataset_ids: list[str],
        asset_classes: list[str],
        tenant_id: str,
        user_id: str,
        request_id: str,
    ) -> dict[str, object]:
        payload = {"datasetIds": dataset_ids, "assetClasses": asset_classes}
        response = await self._post(
            path="/internal/v1/exports/backtest",
            payload=payload,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
        )
        return response

    async def get_backtest_export(
        self,
        *,
        export_id: str,
        tenant_id: str,
        user_id: str,
        request_id: str,
    ) -> dict[str, object] | None:
        response = await self._get(
            path=f"/internal/v1/exports/{export_id}",
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
            allow_not_found=True,
        )
        return response

    async def get_market_context(
        self,
        *,
        asset_classes: list[str],
        tenant_id: str,
        user_id: str,
        request_id: str,
    ) -> dict[str, object]:
        payload = {"assetClasses": asset_classes}
        response = await self._post(
            path="/internal/v1/context/market",
            payload=payload,
            tenant_id=tenant_id,
            user_id=user_id,
            request_id=request_id,
        )
        return response

    async def _post(
        self,
        *,
        path: str,
        payload: dict[str, object],
        tenant_id: str,
        user_id: str,
        request_id: str,
    ) -> dict[str, object]:
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            try:
                response = await client.post(
                    f"{self._base_url}{path}",
                    headers=self._headers(tenant_id=tenant_id, user_id=user_id, request_id=request_id),
                    json=payload,
                )
            except httpx.HTTPError as exc:
                raise AdapterError(str(exc), code="TRADER_DATA_UNAVAILABLE", status_code=502) from exc
        return self._parse_response(response=response, allow_not_found=False)

    async def _get(
        self,
        *,
        path: str,
        tenant_id: str,
        user_id: str,
        request_id: str,
        allow_not_found: bool,
    ) -> dict[str, object] | None:
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            try:
                response = await client.get(
                    f"{self._base_url}{path}",
                    headers=self._headers(tenant_id=tenant_id, user_id=user_id, request_id=request_id),
                )
            except httpx.HTTPError as exc:
                raise AdapterError(str(exc), code="TRADER_DATA_UNAVAILABLE", status_code=502) from exc
        return self._parse_response(response=response, allow_not_found=allow_not_found)

    def _parse_response(self, *, response: httpx.Response, allow_not_found: bool) -> dict[str, object] | None:
        if response.status_code == 404 and allow_not_found:
            return None
        if response.status_code >= 400:
            raise AdapterError(
                response.text or "Trader-data request failed.",
                code="TRADER_DATA_REQUEST_FAILED",
                status_code=response.status_code,
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise AdapterError("Trader-data response must be an object.", code="TRADER_DATA_BAD_RESPONSE")
        return payload

    def _headers(self, *, tenant_id: str, user_id: str, request_id: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._service_api_key}",
            "X-Tenant-Id": tenant_id,
            "X-User-Id": user_id,
            "X-Request-Id": request_id,
        }
