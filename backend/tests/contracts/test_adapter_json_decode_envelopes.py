"""Contract tests for adapter JSON-decode normalization into AdapterError envelopes."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import httpx

from src.platform_api.adapters.data_knowledge_adapter import TraderDataHTTPAdapter
from src.platform_api.adapters.execution_adapter import LiveEngineExecutionAdapter
from src.platform_api.adapters.lona_adapter import AdapterError


def test_live_engine_adapter_maps_non_json_payload_to_adapter_error() -> None:
    async def _run() -> None:
        adapter = LiveEngineExecutionAdapter(
            base_url="http://live-engine.local",
            service_api_key="svc-key",
        )

        async def _fake_request(  # type: ignore[no-untyped-def]
            self,
            method: str,
            url: str,
            headers: dict[str, str] | None = None,
            json: dict[str, object] | None = None,
        ):
            _ = (self, headers, json)
            return httpx.Response(
                status_code=200,
                text="<html>not-json</html>",
                request=httpx.Request(method, url),
            )

        with patch(
            "src.platform_api.adapters.execution_adapter.httpx.AsyncClient.request",
            new=_fake_request,
        ):
            try:
                await adapter._request(
                    method="GET",
                    path="/api/internal/deployments",
                    payload=None,
                    tenant_id="tenant-remediate",
                    user_id="user-remediate",
                )
                raise AssertionError("Expected non-JSON live-engine payload to raise AdapterError.")
            except AdapterError as exc:
                assert exc.code == "LIVE_ENGINE_BAD_RESPONSE_JSON"
                assert exc.status_code == 502

    asyncio.run(_run())


def test_trader_data_adapter_maps_non_json_payload_to_adapter_error() -> None:
    adapter = TraderDataHTTPAdapter(
        base_url="http://trader-data.local",
        service_api_key="svc-key",
    )
    response = httpx.Response(
        status_code=200,
        text="not-json",
        request=httpx.Request("GET", "http://trader-data.local/internal/v1/context/market"),
    )

    try:
        adapter._parse_response(response=response, allow_not_found=False)
        raise AssertionError("Expected non-JSON trader-data payload to raise AdapterError.")
    except AdapterError as exc:
        assert exc.code == "TRADER_DATA_BAD_RESPONSE_JSON"
        assert exc.status_code == 502
