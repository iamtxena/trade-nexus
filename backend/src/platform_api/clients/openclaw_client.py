"""OpenClaw client-lane integration using Platform API contracts only (OC-02)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import httpx


@dataclass(frozen=True)
class OpenClawClientConfig:
    base_url: str
    api_token: str = "test-token"
    api_key: str = "tnx.bot.runtime-openclaw-default.secret-001"
    tenant_id: str = "tenant-apikey-43169556e3a2"
    user_id: str = "user-apikey-8de7078687e2"
    timeout_seconds: float = 20.0


class OpenClawClient:
    """Typed OpenClaw integration surface over canonical Platform API routes."""

    def __init__(
        self,
        *,
        config: OpenClawClientConfig,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._client = http_client or httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
        )
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def create_conversation_session(
        self,
        *,
        topic: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {"channel": "openclaw"}
        if topic is not None:
            payload["topic"] = topic
        if metadata:
            payload["metadata"] = metadata
        response = await self._client.post(
            "/v2/conversations/sessions",
            json=payload,
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def create_conversation_turn(
        self,
        *,
        session_id: str,
        message: str,
        role: str = "user",
        metadata: dict[str, object] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {"role": role, "message": message}
        if metadata:
            payload["metadata"] = metadata
        response = await self._client.post(
            f"/v2/conversations/sessions/{session_id}/turns",
            json=payload,
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def market_scan(
        self,
        *,
        asset_classes: list[str],
        capital: float,
    ) -> dict[str, object]:
        response = await self._client.post(
            "/v1/research/market-scan",
            json={"assetClasses": asset_classes, "capital": capital},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def create_strategy(
        self,
        *,
        name: str,
        description: str,
        provider: str = "xai",
    ) -> dict[str, object]:
        response = await self._client.post(
            "/v1/strategies",
            json={"name": name, "description": description, "provider": provider},
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def run_backtest(
        self,
        *,
        strategy_id: str,
        data_ids: list[str],
        start_date: str,
        end_date: str,
        initial_cash: float,
    ) -> dict[str, object]:
        response = await self._client.post(
            f"/v1/strategies/{strategy_id}/backtests",
            json={
                "dataIds": data_ids,
                "startDate": start_date,
                "endDate": end_date,
                "initialCash": initial_cash,
            },
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_backtest(self, *, backtest_id: str) -> dict[str, object]:
        response = await self._client.get(
            f"/v1/backtests/{backtest_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def create_deployment(
        self,
        *,
        strategy_id: str,
        mode: str,
        capital: float,
        idempotency_key: str,
    ) -> dict[str, object]:
        response = await self._client.post(
            "/v1/deployments",
            json={"strategyId": strategy_id, "mode": mode, "capital": capital},
            headers=self._headers(idempotency_key=idempotency_key),
        )
        response.raise_for_status()
        return response.json()

    async def get_deployment(self, *, deployment_id: str) -> dict[str, object]:
        response = await self._client.get(
            f"/v1/deployments/{deployment_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def place_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float | None,
        deployment_id: str | None,
        idempotency_key: str,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        if price is not None:
            payload["price"] = price
        if deployment_id is not None:
            payload["deploymentId"] = deployment_id
        response = await self._client.post(
            "/v1/orders",
            json=payload,
            headers=self._headers(idempotency_key=idempotency_key),
        )
        response.raise_for_status()
        return response.json()

    async def get_order(self, *, order_id: str) -> dict[str, object]:
        response = await self._client.get(
            f"/v1/orders/{order_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def list_portfolios(self) -> dict[str, object]:
        response = await self._client.get(
            "/v1/portfolios",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    async def get_portfolio(self, *, portfolio_id: str) -> dict[str, object]:
        response = await self._client.get(
            f"/v1/portfolios/{portfolio_id}",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.json()

    def _headers(self, *, idempotency_key: str | None = None) -> dict[str, str]:
        request_id = f"req-openclaw-{uuid4()}"
        headers = {
            "Authorization": f"Bearer {self._config.api_token}",
            "X-API-Key": self._config.api_key,
            "X-Tenant-Id": self._config.tenant_id,
            "X-User-Id": self._config.user_id,
            "X-Request-Id": request_id,
        }
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        return headers
