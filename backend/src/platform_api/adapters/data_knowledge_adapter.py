"""Adapter boundary for trader-data internal service integration."""

from __future__ import annotations

import copy
import math
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


def _coerce_numeric(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        try:
            numeric = float(stripped)
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _coerce_positive_int(value: object) -> int | None:
    numeric = _coerce_numeric(value)
    if numeric is None:
        return None
    as_int = int(numeric)
    if float(as_int) != numeric or as_int <= 0:
        return None
    return as_int


def _normalize_market_context_signals(payload: dict[str, object]) -> list[dict[str, str]]:
    raw_signals = payload.get("signals")
    if not isinstance(raw_signals, list):
        return []

    normalized: list[dict[str, str]] = []
    for entry in raw_signals:
        if not isinstance(entry, dict):
            continue
        raw_name = entry.get("name")
        if not isinstance(raw_name, str):
            continue
        name = raw_name.strip()
        if name == "":
            continue
        raw_value = entry.get("value")
        value = ""
        if isinstance(raw_value, str):
            value = raw_value
        elif raw_value is not None:
            value = str(raw_value)
        normalized.append({"name": name, "value": value})
    return normalized


def _normalize_sentiment_candidate(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None

    normalized: dict[str, object] = {}
    score = _coerce_numeric(payload.get("score"))
    if score is None:
        score = _coerce_numeric(payload.get("value"))
    if score is not None:
        normalized["score"] = score

    confidence = _coerce_numeric(payload.get("confidence"))
    if confidence is not None:
        normalized["confidence"] = confidence

    source = payload.get("source")
    if isinstance(source, str):
        source_value = source.strip()
        if source_value != "":
            normalized["source"] = source_value

    source_count = _coerce_positive_int(payload.get("sourceCount"))
    if source_count is not None:
        normalized["sourceCount"] = source_count

    lookback_hours = _coerce_positive_int(payload.get("lookbackHours"))
    if lookback_hours is None:
        lookback_hours = _coerce_positive_int(payload.get("windowHours"))
    if lookback_hours is not None:
        normalized["lookbackHours"] = lookback_hours

    if "score" not in normalized and "confidence" not in normalized:
        return None
    return normalized


def _normalize_sentiment_from_signals(signals: list[dict[str, str]]) -> dict[str, object] | None:
    score: float | None = None
    confidence: float | None = None
    for signal in signals:
        name = signal["name"].strip().lower()
        value = _coerce_numeric(signal["value"])
        if value is None:
            continue
        if name in {"sentiment", "sentiment_score"}:
            score = value
        elif name == "sentiment_confidence":
            confidence = value

    if score is None and confidence is None:
        return None

    result: dict[str, object] = {}
    if score is not None:
        result["score"] = score
    if confidence is not None:
        result["confidence"] = confidence
    return result


def _upsert_signal(signals: list[dict[str, str]], *, name: str, value: str) -> None:
    for signal in signals:
        if signal["name"].strip().lower() == name.lower():
            signal["value"] = value
            return
    signals.append({"name": name, "value": value})


def normalize_market_context_payload(payload: dict[str, object]) -> dict[str, object]:
    normalized = copy.deepcopy(payload)
    if not isinstance(normalized.get("regimeSummary"), str):
        normalized["regimeSummary"] = "Context unavailable."

    normalized_signals = _normalize_market_context_signals(normalized)
    if normalized_signals:
        normalized["signals"] = normalized_signals
    elif "signals" in normalized:
        normalized["signals"] = []

    raw_ml_signals = normalized.get("mlSignals")
    ml_signals: dict[str, object] = copy.deepcopy(raw_ml_signals) if isinstance(raw_ml_signals, dict) else {}

    sentiment = _normalize_sentiment_candidate(ml_signals.get("sentiment"))
    if sentiment is None:
        sentiment = _normalize_sentiment_candidate(normalized.get("sentiment"))
    if sentiment is None:
        sentiment = _normalize_sentiment_from_signals(normalized_signals)

    if sentiment is not None:
        ml_signals["sentiment"] = sentiment
        normalized.pop("sentiment", None)
        if "score" in sentiment:
            _upsert_signal(
                normalized_signals,
                name="sentiment_score",
                value=str(sentiment["score"]),
            )
        if "confidence" in sentiment:
            _upsert_signal(
                normalized_signals,
                name="sentiment_confidence",
                value=str(sentiment["confidence"]),
            )

    if ml_signals:
        normalized["mlSignals"] = ml_signals
    else:
        normalized.pop("mlSignals", None)

    if normalized_signals:
        normalized["signals"] = normalized_signals

    return normalized


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
            payload = await self._inner_adapter.get_market_context(
                asset_classes=asset_classes,
                tenant_id=tenant_id,
                user_id=user_id,
                request_id=request_id,
            )
            if not isinstance(payload, dict):
                raise AdapterError("Trader-data market context response must be an object.", code="TRADER_DATA_BAD_RESPONSE")
            return normalize_market_context_payload(payload)

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
        payload = normalize_market_context_payload(payload)

        store_time = monotonic()
        self._evict_expired(now=store_time)
        if len(self._market_context_cache) >= self._max_entries:
            # Deterministic eviction: drop entry with the earliest expiration.
            oldest = min(self._market_context_cache.items(), key=lambda item: item[1][0])[0]
            self._market_context_cache.pop(oldest, None)
        self._market_context_cache[cache_key] = (store_time + self._ttl_seconds, copy.deepcopy(payload))
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
            "sentiment": {
                "score": 0.58,
                "confidence": 0.66,
                "source": "curated-news+social",
                "sourceCount": 124,
                "lookbackHours": 24,
            },
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
