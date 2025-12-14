"""Data ingestion service."""

from typing import Any

import httpx


class DataService:
    """Service for fetching market data.

    Note: This is a stub. In production, connect to actual data sources
    like Coinbase, Binance, or data providers.
    """

    def __init__(self) -> None:
        self.client = httpx.AsyncClient()

    async def get_price(self, symbol: str) -> dict[str, Any]:
        """Get current price for a symbol."""
        # Stub implementation
        # In production, call actual API
        return {
            "symbol": symbol,
            "price": 50000.0 if symbol == "BTC" else 3000.0,
            "change_24h": 2.5,
            "volume_24h": 1000000000,
        }

    async def get_historical_prices(
        self, symbol: str, days: int = 30
    ) -> list[dict[str, Any]]:
        """Get historical price data."""
        # Stub implementation
        import random
        from datetime import datetime, timedelta

        base_price = 50000.0 if symbol == "BTC" else 3000.0
        prices = []

        for i in range(days):
            date = datetime.now() - timedelta(days=days - i)
            price = base_price * (1 + random.uniform(-0.05, 0.05))
            prices.append(
                {
                    "date": date.isoformat(),
                    "open": price,
                    "high": price * 1.02,
                    "low": price * 0.98,
                    "close": price * (1 + random.uniform(-0.01, 0.01)),
                    "volume": random.uniform(1e9, 2e9),
                }
            )

        return prices

    async def get_market_summary(self) -> dict[str, Any]:
        """Get market summary."""
        return {
            "total_market_cap": 2500000000000,
            "total_volume_24h": 100000000000,
            "btc_dominance": 52.5,
            "fear_greed_index": 55,
        }

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
