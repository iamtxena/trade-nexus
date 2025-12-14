"""Prediction schemas."""

from typing import Any

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    """Request for ML prediction."""

    symbol: str = Field(..., description="Trading symbol (e.g., BTC, ETH)")
    prediction_type: str = Field(..., description="Type: price, volatility, sentiment, trend")
    timeframe: str = Field(default="24h", description="Prediction timeframe")
    features: dict[str, float] | None = Field(default=None, description="Additional features")


class PredictionResponse(BaseModel):
    """Response with ML prediction."""

    symbol: str
    prediction_type: str
    value: dict[str, Any]
    confidence: float = Field(..., ge=0, le=100)
    timeframe: str


class AnomalyRequest(BaseModel):
    """Request for anomaly detection."""

    symbol: str
    data: list[float] = Field(..., description="Time series data to check")


class AnomalyResponse(BaseModel):
    """Response with anomaly detection result."""

    symbol: str
    is_anomaly: bool
    score: float = Field(..., ge=0, le=1)
    details: dict[str, Any] | None = None


class OptimizationRequest(BaseModel):
    """Request for portfolio optimization."""

    holdings: dict[str, float] = Field(..., description="Current holdings {symbol: quantity}")
    predictions: list[dict[str, Any]] = Field(..., description="ML predictions for assets")
    constraints: dict[str, Any] | None = Field(
        default=None, description="Optimization constraints"
    )


class OptimizationResponse(BaseModel):
    """Response with optimized allocation."""

    allocations: dict[str, float] = Field(..., description="Target allocations {symbol: weight}")
    expected_return: float
    risk_score: float = Field(..., ge=0, le=100)
