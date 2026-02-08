"""Async HTTP client for Lona Gateway API."""

import asyncio
import csv
import io
import logging
from datetime import UTC, datetime
from types import TracebackType
from typing import Any

import httpx

from src.config import Settings, get_settings
from src.schemas.lona import (
    LonaBacktestRequest,
    LonaBacktestResponse,
    LonaRegistrationRequest,
    LonaRegistrationResponse,
    LonaReport,
    LonaReportStatus,
    LonaStrategy,
    LonaStrategyCreateRequest,
    LonaStrategyFromDescriptionResponse,
    LonaSymbol,
)

logger = logging.getLogger(__name__)

# Binance REST API for historical klines
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
BINANCE_INTERVAL_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}
BINANCE_MAX_LIMIT = 1000


class LonaClientError(Exception):
    """Base error for Lona client operations."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LonaClient:
    """Async HTTP client for Lona Gateway API.

    All Lona API responses wrap data in { "data": T }.
    This client automatically unwraps the data envelope.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._token: str = self._settings.lona_agent_token
        self._client = httpx.AsyncClient(
            base_url=self._settings.lona_gateway_url,
            timeout=httpx.Timeout(60.0),
        )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def register(self) -> LonaRegistrationResponse:
        """Register agent with Lona Gateway using registration secret.

        POST /api/v1/agents/register
        Stores token for subsequent authenticated calls.
        """
        body = LonaRegistrationRequest(
            agent_id=self._settings.lona_agent_id,
            agent_name=self._settings.lona_agent_name,
            expires_in_days=self._settings.lona_token_ttl_days,
        )
        response = await self._client.post(
            "/api/v1/agents/register",
            json=body.model_dump(),
            headers={"X-Agent-Registration-Secret": self._settings.lona_agent_registration_secret},
        )
        self._raise_for_status(response)
        data = self._unwrap(response.json())
        registration = LonaRegistrationResponse(**data)
        self._token = registration.token
        logger.info("Registered agent %s with Lona Gateway", self._settings.lona_agent_id)
        return registration

    # ------------------------------------------------------------------
    # Internal request helpers
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        """Make an authenticated request and unwrap the { data: T } envelope."""
        headers: dict[str, str] = kwargs.pop("headers", {})
        headers["X-API-Key"] = self._token
        headers["X-User-Id"] = self._settings.lona_agent_id

        response = await self._client.request(method, path, headers=headers, **kwargs)
        self._raise_for_status(response)
        return self._unwrap(response.json())

    async def _request_raw(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Make an authenticated request and return the raw response."""
        headers: dict[str, str] = kwargs.pop("headers", {})
        headers["X-API-Key"] = self._token
        headers["X-User-Id"] = self._settings.lona_agent_id

        response = await self._client.request(method, path, headers=headers, **kwargs)
        self._raise_for_status(response)
        return response

    @staticmethod
    def _unwrap(body: dict) -> dict:
        """Unwrap the Lona { data: T } response envelope."""
        if isinstance(body, dict) and "data" in body:
            return body["data"]
        return body

    # ------------------------------------------------------------------
    # Strategy methods
    # ------------------------------------------------------------------

    async def create_strategy_from_description(
        self,
        description: str,
        name: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> LonaStrategyFromDescriptionResponse:
        """Create a strategy from a natural language description via AI agent.

        POST /api/v1/agent/strategy/create
        Timeout: 180s (AI code generation is slow)
        """
        body: dict[str, Any] = {"description": description}
        if name:
            body["name"] = name
        if provider:
            body["provider"] = provider
        if model:
            body["model"] = model

        old_timeout = self._client.timeout
        self._client.timeout = httpx.Timeout(180.0)
        try:
            data = await self._request("POST", "/api/v1/agent/strategy/create", json=body)
        finally:
            self._client.timeout = old_timeout

        return LonaStrategyFromDescriptionResponse(**data)

    async def create_strategy(self, name: str, code: str, description: str | None = None) -> dict:
        """Upload an existing strategy as code.

        POST /api/v1/strategies
        Returns { id: str }
        """
        body = LonaStrategyCreateRequest(name=name, code=code, description=description)
        return await self._request("POST", "/api/v1/strategies", json=body.model_dump())

    async def list_strategies(self, skip: int = 0, limit: int = 50) -> list[LonaStrategy]:
        """List all strategies.

        GET /api/v1/strategies
        Returns paginated { items: [], has_next, total }
        """
        data = await self._request("GET", "/api/v1/strategies", params={"skip": skip, "limit": limit})
        items = data.get("items", [])
        return [LonaStrategy(**item) for item in items]

    async def get_strategy(self, strategy_id: str) -> LonaStrategy:
        """Get strategy details by ID.

        GET /api/v1/strategies/{strategy_id}
        """
        data = await self._request("GET", f"/api/v1/strategies/{strategy_id}")
        return LonaStrategy(**data)

    async def get_strategy_code(self, strategy_id: str) -> str:
        """Get strategy source code.

        GET /api/v1/strategies/{strategy_id}/code
        """
        data = await self._request("GET", f"/api/v1/strategies/{strategy_id}/code")
        return data.get("code", "")

    # ------------------------------------------------------------------
    # Symbol methods
    # ------------------------------------------------------------------

    async def list_symbols(self, is_global: bool = False, limit: int = 50, skip: int = 0) -> list[LonaSymbol]:
        """List available data symbols.

        GET /api/v1/symbols
        Returns paginated { items: [], has_next, total }
        """
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if is_global:
            params["is_global"] = True
        data = await self._request("GET", "/api/v1/symbols", params=params)
        items = data.get("items", [])
        return [LonaSymbol(**item) for item in items]

    async def get_symbol(self, symbol_id: str) -> LonaSymbol:
        """Get symbol details by ID.

        GET /api/v1/symbols/{symbol_id}
        """
        data = await self._request("GET", f"/api/v1/symbols/{symbol_id}")
        return LonaSymbol(**data)

    async def upload_symbol(self, csv_content: bytes, metadata: dict) -> dict:
        """Upload market data as CSV to Lona.

        POST /api/v1/symbols (multipart/form-data)
        """
        import json as json_mod

        files = {"file": ("data.csv", csv_content, "text/csv")}
        form_data = {"metadata": json_mod.dumps(metadata)}

        headers: dict[str, str] = {
            "X-API-Key": self._token,
            "X-User-Id": self._settings.lona_agent_id,
        }

        old_timeout = self._client.timeout
        self._client.timeout = httpx.Timeout(60.0)
        try:
            response = await self._client.post(
                "/api/v1/symbols",
                files=files,
                data=form_data,
                headers=headers,
            )
        finally:
            self._client.timeout = old_timeout

        self._raise_for_status(response)
        return self._unwrap(response.json())

    async def download_market_data(
        self, symbol: str, interval: str, start_date: str, end_date: str
    ) -> LonaSymbol:
        """Download market data from Binance and upload to Lona.

        This replicates the MCP server's lona_download_market_data flow:
        1. Fetch klines from Binance REST API
        2. Convert to CSV
        3. Upload as multipart to POST /api/v1/symbols
        """
        # Fetch from Binance
        candles = await self._fetch_binance_klines(symbol, interval, start_date, end_date)
        logger.info("Downloaded %d candles for %s (%s)", len(candles), symbol, interval)

        # Convert to CSV
        csv_content = self._candles_to_csv(candles)

        # Upload to Lona
        metadata = {
            "data_type": "ohlcv",
            "name": symbol,
            "exchange": "BINANCE",
            "asset_class": "crypto",
            "quote_currency": "USD",
            "column_mapping": {
                "timestamp": "timestamp",
                "open": "open",
                "high": "high",
                "low": "low",
                "close": "close",
                "volume": "volume",
            },
            "frequency": interval,
            "timezone": "UTC",
            "description": f"{symbol} {interval} candles from Binance ({start_date} to {end_date})",
        }

        data = await self.upload_symbol(csv_content, metadata)
        symbol_id = data.get("id", "")
        if symbol_id:
            return await self.get_symbol(symbol_id)
        return LonaSymbol(id=symbol_id, name=symbol)

    async def _fetch_binance_klines(
        self, symbol: str, interval: str, start_date: str, end_date: str
    ) -> list[list]:
        """Fetch historical klines from Binance API with pagination."""
        start_ms = int(datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp() * 1000)
        end_ms = int(datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC).timestamp() * 1000)

        all_candles: list[list] = []
        current_start = start_ms

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as binance_client:
            while current_start < end_ms:
                params = {
                    "symbol": symbol.upper(),
                    "interval": interval,
                    "startTime": current_start,
                    "endTime": end_ms,
                    "limit": BINANCE_MAX_LIMIT,
                }
                response = await binance_client.get(BINANCE_KLINES_URL, params=params)
                if response.status_code != 200:
                    raise LonaClientError(
                        f"Binance API error {response.status_code}: {response.text}",
                        status_code=response.status_code,
                    )

                batch = response.json()
                if not batch:
                    break

                all_candles.extend(batch)

                # Move start to after the last candle
                last_close_time = batch[-1][6]  # Close time
                current_start = last_close_time + 1

                if len(batch) < BINANCE_MAX_LIMIT:
                    break

        return all_candles

    @staticmethod
    def _candles_to_csv(candles: list[list]) -> bytes:
        """Convert Binance klines to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])

        for candle in candles:
            # Binance kline format: [open_time, open, high, low, close, volume, ...]
            ts = datetime.fromtimestamp(candle[0] / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([ts, candle[1], candle[2], candle[3], candle[4], candle[5]])

        return output.getvalue().encode("utf-8")

    # ------------------------------------------------------------------
    # Backtest methods
    # ------------------------------------------------------------------

    async def run_backtest(self, request: LonaBacktestRequest) -> LonaBacktestResponse:
        """Run a backtest asynchronously. Returns a report_id for polling.

        POST /api/v1/runner/run
        """
        data = await self._request("POST", "/api/v1/runner/run", json=request.model_dump(exclude_none=True))
        return LonaBacktestResponse(**data)

    async def get_report_status(self, report_id: str) -> LonaReportStatus:
        """Poll the status of a backtest report.

        GET /api/v1/reports/{report_id}/status
        """
        data = await self._request("GET", f"/api/v1/reports/{report_id}/status")
        return LonaReportStatus(**data)

    async def get_report(self, report_id: str) -> LonaReport:
        """Get the backtest report.

        GET /api/v1/reports/{report_id}
        """
        data = await self._request("GET", f"/api/v1/reports/{report_id}")
        return LonaReport(**data)

    async def get_full_report(self, report_id: str) -> dict:
        """Get the detailed backtest report including trade history.

        GET /api/v1/reports/{report_id}/full
        """
        old_timeout = self._client.timeout
        self._client.timeout = httpx.Timeout(60.0)
        try:
            return await self._request("GET", f"/api/v1/reports/{report_id}/full")
        finally:
            self._client.timeout = old_timeout

    async def wait_for_report(
        self, report_id: str, timeout: int = 300, poll_interval: int = 5
    ) -> LonaReport:
        """Poll until a report completes or the timeout is reached."""
        elapsed = 0
        while elapsed < timeout:
            status = await self.get_report_status(report_id)
            logger.debug("Report %s status: %s", report_id, status.status)

            if status.status in ("COMPLETED", "completed"):
                return await self.get_report(report_id)

            if status.status in ("FAILED", "failed"):
                report = await self.get_report(report_id)
                raise LonaClientError(
                    f"Backtest report {report_id} failed: {report.error or 'unknown error'}",
                )

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise LonaClientError(
            f"Timed out waiting for report {report_id} after {timeout}s",
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "LonaClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        """Raise LonaClientError for non-2xx responses."""
        if response.is_success:
            return

        try:
            body = response.json()
            # Lona error format: { error: { code, message } }
            error = body.get("error", {})
            if isinstance(error, dict):
                detail = error.get("message", response.text)
            else:
                detail = body.get("detail", response.text)
        except Exception:
            detail = response.text

        raise LonaClientError(
            f"Lona API error {response.status_code}: {detail}",
            status_code=response.status_code,
        )
