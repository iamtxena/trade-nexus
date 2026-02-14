"""Adapter boundary for trader-data internal service integration."""

from __future__ import annotations

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
