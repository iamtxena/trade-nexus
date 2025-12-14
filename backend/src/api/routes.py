"""API routes."""

from fastapi import APIRouter, HTTPException

from src.agents.graph import run_prediction_graph, run_anomaly_graph, run_optimization_graph
from src.schemas.predictions import (
    AnomalyRequest,
    AnomalyResponse,
    OptimizationRequest,
    OptimizationResponse,
    PredictionRequest,
    PredictionResponse,
)

router = APIRouter()


@router.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest) -> PredictionResponse:
    """Generate ML prediction for a symbol."""
    try:
        result = await run_prediction_graph(
            symbol=request.symbol,
            prediction_type=request.prediction_type,
            timeframe=request.timeframe,
            features=request.features,
        )
        return PredictionResponse(
            symbol=request.symbol,
            prediction_type=request.prediction_type,
            value=result["value"],
            confidence=result["confidence"],
            timeframe=request.timeframe,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/anomaly", response_model=AnomalyResponse)
async def check_anomaly(request: AnomalyRequest) -> AnomalyResponse:
    """Check for market anomalies."""
    try:
        result = await run_anomaly_graph(
            symbol=request.symbol,
            data=request.data,
        )
        return AnomalyResponse(
            symbol=request.symbol,
            is_anomaly=result["is_anomaly"],
            score=result["score"],
            details=result.get("details"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize", response_model=OptimizationResponse)
async def optimize_portfolio(request: OptimizationRequest) -> OptimizationResponse:
    """Optimize portfolio allocation."""
    try:
        result = await run_optimization_graph(
            holdings=request.holdings,
            predictions=request.predictions,
            constraints=request.constraints,
        )
        return OptimizationResponse(
            allocations=result["allocations"],
            expected_return=result["expected_return"],
            risk_score=result["risk_score"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "trade-nexus-ml"}
