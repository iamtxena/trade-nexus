"""Lona Gateway schemas."""

from typing import Any, Literal  # noqa: I001

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Authentication
# ------------------------------------------------------------------

class LonaRegistrationRequest(BaseModel):
    """Request to register an agent with Lona Gateway."""

    agent_id: str = Field(..., description="Unique identifier for the agent")
    agent_name: str = Field(default="", description="Human-readable agent name")
    source: str = Field(default="trade-nexus", description="Source system identifier")
    expires_in_days: int = Field(default=30, description="Token expiration in days")


class LonaRegistrationResponse(BaseModel):
    """Response from Lona Gateway registration (unwrapped from data envelope)."""

    token: str = Field(..., description="Authentication token for API access")
    partner_id: str = Field(..., description="Assigned partner identifier")
    partner_name: str = Field(..., description="Partner display name")
    permissions: list[str] = Field(..., description="Granted permission scopes")
    expires_at: str = Field(..., description="Token expiration timestamp (ISO 8601)")


# ------------------------------------------------------------------
# Strategies
# ------------------------------------------------------------------

class LonaStrategyCreateRequest(BaseModel):
    """Request to create a strategy by uploading code directly."""

    name: str = Field(..., description="Strategy name")
    code: str = Field(..., description="Strategy source code (Backtrader Python)")
    description: str | None = Field(default=None, description="Optional strategy description")
    version: str = Field(default="1.0.0", description="Strategy version")
    language: str = Field(default="python", description="Code language")


class LonaStrategyFromDescriptionRequest(BaseModel):
    """Request to create a strategy from natural language description via AI agent."""

    description: str = Field(..., min_length=10, description="Natural language strategy description")
    name: str | None = Field(default=None, description="Optional strategy name")
    provider: str | None = Field(default=None, description="AI provider (xai, openai, anthropic, google)")
    model: str | None = Field(default=None, description="AI model override")


class LonaStrategyFromDescriptionResponse(BaseModel):
    """Response from AI-powered strategy creation."""

    model_config = {"populate_by_name": True}

    strategy_id: str = Field(..., alias="strategyId", description="Created strategy ID")
    name: str = Field(..., description="Strategy name")
    code: str = Field(..., description="Generated Backtrader code")
    explanation: str = Field(..., description="Explanation of the strategy logic")


class LonaStrategy(BaseModel):
    """Lona strategy details."""

    id: str = Field(..., description="Strategy identifier")
    name: str = Field(..., description="Strategy name")
    description: str = Field(default="", description="Strategy description")
    version: str = Field(default="", description="Strategy version")
    version_id: str = Field(default="", description="Version identifier")
    language: str = Field(default="python", description="Code language")
    code: str = Field(default="", description="Strategy source code")
    user_id: str = Field(default="", description="Owner user ID")
    created_at: str = Field(default="", description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(default="", description="Last update timestamp (ISO 8601)")


# ------------------------------------------------------------------
# Symbols (Market Data)
# ------------------------------------------------------------------

class LonaSymbolDataRange(BaseModel):
    """Date range of available data for a symbol."""

    start_timestamp: str | None = Field(default=None, description="Data start")
    end_timestamp: str | None = Field(default=None, description="Data end")


class LonaSymbolTypeMetadata(BaseModel):
    """Type-specific metadata for a symbol."""

    data_type: str = Field(default="ohlcv", description="Data type")
    exchange: str | None = Field(default=None, description="Exchange name")
    asset_class: str | None = Field(default=None, description="Asset class")
    quote_currency: str | None = Field(default=None, description="Quote currency")
    column_mapping: dict[str, str | None] = Field(default_factory=dict, description="Column mapping")


class LonaSymbol(BaseModel):
    """Market symbol available in Lona."""

    id: str = Field(..., description="Symbol identifier")
    name: str = Field(..., description="Symbol display name")
    description: str = Field(default="", description="Symbol description")
    is_global: bool = Field(default=False, description="Whether globally available")
    data_range: LonaSymbolDataRange | None = Field(default=None, description="Available data range")
    frequencies: list[str] = Field(default_factory=list, description="Available frequencies")
    type_metadata: LonaSymbolTypeMetadata | None = Field(default=None, description="Type metadata")
    created_at: str = Field(default="", description="Creation timestamp")
    updated_at: str = Field(default="", description="Last update timestamp")


class LonaDataDownloadRequest(BaseModel):
    """Request to download market data from Binance."""

    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    interval: str = Field(default="1h", description="Data interval (1m, 5m, 15m, 30m, 1h, 4h, 1d)")
    start_date: str = Field(..., description="Download start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Download end date (YYYY-MM-DD)")


# ------------------------------------------------------------------
# Backtesting
# ------------------------------------------------------------------

class LonaCommissionSchema(BaseModel):
    """Commission configuration for backtesting."""

    commission: float = Field(default=0.001, description="Commission rate per trade")
    leverage: float = Field(default=1, description="Leverage multiplier")


class LonaSimulationParameters(BaseModel):
    """Simulation parameters for backtesting."""

    initial_cash: float = Field(default=100000, description="Starting capital")
    commission_schema: LonaCommissionSchema = Field(default_factory=LonaCommissionSchema)
    buy_on_close: bool = Field(default=True, description="Execute buys at close price")


class LonaBacktestRequest(BaseModel):
    """Request to run a backtest via Lona runner."""

    strategy_id: str = Field(..., description="Strategy to backtest")
    data_ids: list[str] = Field(..., description="Market data symbol IDs to use")
    start_date: str = Field(..., description="Backtest start date")
    end_date: str = Field(..., description="Backtest end date")
    parameters: list[dict[str, Any]] | None = Field(default=None, description="Strategy parameters")
    simulation_parameters: LonaSimulationParameters = Field(default_factory=LonaSimulationParameters)


class LonaBacktestResponse(BaseModel):
    """Response from backtest submission."""

    report_id: str = Field(..., description="Report identifier for tracking")


# ------------------------------------------------------------------
# Reports
# ------------------------------------------------------------------

class LonaReportStatus(BaseModel):
    """Status of a Lona backtest report."""

    status: Literal["PENDING", "EXECUTING", "PROCESSING", "COMPLETED", "FAILED"] = Field(
        ..., description="Current report processing status"
    )
    progress: float | None = Field(default=None, description="Completion progress (0-1)")


class LonaReport(BaseModel):
    """Lona backtest report."""

    id: str = Field(..., description="Report identifier")
    strategy_id: str = Field(..., description="Strategy that was backtested")
    status: str = Field(..., description="Report processing status")
    name: str = Field(default="", description="Report name")
    description: str = Field(default="", description="Report description")
    created_at: str = Field(default="", description="Creation timestamp")
    updated_at: str = Field(default="", description="Last update timestamp")
    total_stats: dict[str, Any] | None = Field(default=None, description="Performance statistics")
    error: str | None = Field(default=None, description="Error message if failed")


# ------------------------------------------------------------------
# Portfolio (internal, not Lona API)
# ------------------------------------------------------------------

class PortfolioAllocation(BaseModel):
    """Single asset allocation within a portfolio plan."""

    asset: str = Field(..., description="Asset identifier or symbol")
    weight: float = Field(..., ge=0, le=1, description="Portfolio weight (0-1)")
    strategy_id: str | None = Field(default=None, description="Associated strategy identifier")
    rationale: str = Field(..., description="Reasoning for this allocation")


class PortfolioPlan(BaseModel):
    """Complete portfolio allocation plan."""

    allocations: list[PortfolioAllocation] = Field(..., description="Asset allocations")
    total_capital: float = Field(..., description="Total capital to allocate")
    risk_level: Literal["conservative", "moderate", "aggressive"] = Field(
        ..., description="Portfolio risk level"
    )
    expected_monthly_return: float | None = Field(
        default=None, description="Expected monthly return percentage"
    )
