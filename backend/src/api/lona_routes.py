"""Lona Gateway API routes."""

import logging

from fastapi import APIRouter, HTTPException

from src.schemas.lona import (
    LonaBacktestRequest,
    LonaBacktestResponse,
    LonaDataDownloadRequest,
    LonaRegistrationResponse,
    LonaReport,
    LonaReportStatus,
    LonaStrategy,
    LonaStrategyFromDescriptionRequest,
    LonaStrategyFromDescriptionResponse,
    LonaSymbol,
)
from src.services.lona_client import LonaClient, LonaClientError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lona", tags=["lona"])

# Module-level token cache so registration persists across requests.
_cached_token: str | None = None


def _get_client() -> LonaClient:
    """Create a LonaClient, injecting the cached token if available."""
    client = LonaClient()
    if _cached_token:
        client._token = _cached_token
    return client


@router.post("/register", response_model=LonaRegistrationResponse)
async def register_agent() -> LonaRegistrationResponse:
    """Register trade-nexus agent with Lona Gateway."""
    global _cached_token
    async with LonaClient() as client:
        try:
            result = await client.register()
            _cached_token = result.token
            return result
        except LonaClientError as e:
            raise HTTPException(status_code=e.status_code or 502, detail=str(e))


@router.post("/strategy/create-from-description", response_model=LonaStrategyFromDescriptionResponse)
async def create_strategy_from_description(
    request: LonaStrategyFromDescriptionRequest,
) -> LonaStrategyFromDescriptionResponse:
    """Create a strategy from natural language description via Lona AI agent."""
    async with _get_client() as client:
        try:
            return await client.create_strategy_from_description(
                description=request.description,
                name=request.name,
            )
        except LonaClientError as e:
            raise HTTPException(status_code=e.status_code or 502, detail=str(e))


@router.get("/strategies", response_model=list[LonaStrategy])
async def list_strategies() -> list[LonaStrategy]:
    """List all strategies."""
    async with _get_client() as client:
        try:
            return await client.list_strategies()
        except LonaClientError as e:
            raise HTTPException(status_code=e.status_code or 502, detail=str(e))


@router.get("/strategy/{strategy_id}", response_model=LonaStrategy)
async def get_strategy(strategy_id: str) -> LonaStrategy:
    """Get strategy details."""
    async with _get_client() as client:
        try:
            return await client.get_strategy(strategy_id)
        except LonaClientError as e:
            raise HTTPException(status_code=e.status_code or 502, detail=str(e))


@router.post("/backtest", response_model=LonaBacktestResponse)
async def run_backtest(request: LonaBacktestRequest) -> LonaBacktestResponse:
    """Run backtest via Lona runner."""
    async with _get_client() as client:
        try:
            return await client.run_backtest(request)
        except LonaClientError as e:
            raise HTTPException(status_code=e.status_code or 502, detail=str(e))


@router.get("/report/{report_id}/status", response_model=LonaReportStatus)
async def get_report_status(report_id: str) -> LonaReportStatus:
    """Check backtest report status."""
    async with _get_client() as client:
        try:
            return await client.get_report_status(report_id)
        except LonaClientError as e:
            raise HTTPException(status_code=e.status_code or 502, detail=str(e))


@router.get("/report/{report_id}", response_model=LonaReport)
async def get_report(report_id: str) -> LonaReport:
    """Get backtest report."""
    async with _get_client() as client:
        try:
            return await client.get_report(report_id)
        except LonaClientError as e:
            raise HTTPException(status_code=e.status_code or 502, detail=str(e))


@router.get("/symbols", response_model=list[LonaSymbol])
async def list_symbols(is_global: bool = False, limit: int = 50) -> list[LonaSymbol]:
    """List available market data symbols."""
    async with _get_client() as client:
        try:
            return await client.list_symbols(is_global=is_global, limit=limit)
        except LonaClientError as e:
            raise HTTPException(status_code=e.status_code or 502, detail=str(e))


@router.post("/data/download", response_model=LonaSymbol)
async def download_market_data(request: LonaDataDownloadRequest) -> LonaSymbol:
    """Download market data from Binance and upload to Lona."""
    async with _get_client() as client:
        try:
            return await client.download_market_data(
                symbol=request.symbol,
                interval=request.interval,
                start_date=request.start_date,
                end_date=request.end_date,
            )
        except LonaClientError as e:
            raise HTTPException(status_code=e.status_code or 502, detail=str(e))



# Note: The Strategist Brain pipeline has been moved to the TypeScript frontend.
# Use the Next.js API route POST /api/strategist instead.
