"""LangGraph orchestration for agents."""

from typing import Any

from src.agents.anomaly import AnomalyAgent
from src.agents.optimizer import OptimizerAgent
from src.agents.predictor import PredictorAgent
from src.agents.strategist import StrategistAgent

# Initialize agents
_predictor_agent: PredictorAgent | None = None
_anomaly_agent: AnomalyAgent | None = None
_optimizer_agent: OptimizerAgent | None = None
_strategist_agent: StrategistAgent | None = None


def get_predictor_agent() -> PredictorAgent:
    """Get or create predictor agent."""
    global _predictor_agent
    if _predictor_agent is None:
        _predictor_agent = PredictorAgent()
    return _predictor_agent


def get_anomaly_agent() -> AnomalyAgent:
    """Get or create anomaly agent."""
    global _anomaly_agent
    if _anomaly_agent is None:
        _anomaly_agent = AnomalyAgent()
    return _anomaly_agent


def get_optimizer_agent() -> OptimizerAgent:
    """Get or create optimizer agent."""
    global _optimizer_agent
    if _optimizer_agent is None:
        _optimizer_agent = OptimizerAgent()
    return _optimizer_agent


def get_strategist_agent() -> StrategistAgent:
    """Get or create strategist agent."""
    global _strategist_agent
    if _strategist_agent is None:
        _strategist_agent = StrategistAgent()
    return _strategist_agent


async def run_prediction_graph(
    symbol: str,
    prediction_type: str,
    timeframe: str,
    features: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Run prediction graph."""
    agent = get_predictor_agent()
    return await agent.run(
        symbol=symbol,
        prediction_type=prediction_type,
        timeframe=timeframe,
        features=features,
    )


async def run_anomaly_graph(
    symbol: str,
    data: list[float],
) -> dict[str, Any]:
    """Run anomaly detection graph."""
    agent = get_anomaly_agent()
    return await agent.run(symbol=symbol, data=data)


async def run_optimization_graph(
    holdings: dict[str, float],
    predictions: list[dict[str, Any]],
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run portfolio optimization graph."""
    agent = get_optimizer_agent()
    return await agent.run(
        holdings=holdings,
        predictions=predictions,
        constraints=constraints,
    )


async def run_strategist_graph(
    asset_classes: list[str] | None = None,
    capital: float | None = None,
) -> dict[str, Any]:
    """Run strategist brain pipeline."""
    agent = get_strategist_agent()
    return await agent.run(
        asset_classes=asset_classes,
        capital=capital,
    )
