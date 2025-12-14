"""Portfolio optimization agent."""

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_xai import ChatXAI

from src.config import get_settings


class OptimizerState(TypedDict):
    """State for optimization agent."""

    holdings: dict[str, float]
    predictions: list[dict[str, Any]]
    constraints: dict[str, Any] | None
    analysis: str | None
    allocations: dict[str, float]
    expected_return: float
    risk_score: float


class OptimizerAgent:
    """Agent for portfolio optimization."""

    def __init__(self) -> None:
        settings = get_settings()
        self.llm = ChatXAI(
            model="grok-2-latest",
            api_key=settings.xai_api_key,
        )

    async def analyze_portfolio(self, state: OptimizerState) -> OptimizerState:
        """Analyze current portfolio and predictions."""
        messages = [
            SystemMessage(
                content="""You are a portfolio optimization agent. Analyze the current
                holdings and ML predictions to suggest optimal allocation. Consider:
                - Risk-adjusted returns
                - Diversification
                - Position sizing"""
            ),
            HumanMessage(
                content=f"""Current portfolio:
                - Holdings: {state['holdings']}
                - Predictions: {state['predictions']}
                - Constraints: {state.get('constraints', {})}

                Provide allocation analysis."""
            ),
        ]

        response = await self.llm.ainvoke(messages)
        state["analysis"] = response.content
        return state

    async def optimize(self, state: OptimizerState) -> OptimizerState:
        """Calculate optimal allocations."""
        holdings = state["holdings"]
        predictions = state["predictions"]

        if not holdings or not predictions:
            # Default to equal allocation
            symbols = list(holdings.keys()) if holdings else ["BTC", "ETH"]
            equal_weight = 1.0 / len(symbols)
            state["allocations"] = {s: equal_weight for s in symbols}
            state["expected_return"] = 0.0
            state["risk_score"] = 50.0
            return state

        # Simple momentum-based allocation
        allocations: dict[str, float] = {}
        total_score = 0.0

        for pred in predictions:
            symbol = pred.get("symbol", "")
            confidence = pred.get("confidence", 50) / 100.0
            value = pred.get("value", {})

            # Extract directional signal
            if isinstance(value, dict):
                direction = value.get("direction", "neutral")
                score = confidence if direction == "bullish" else (1 - confidence)
            else:
                score = confidence

            allocations[symbol] = score
            total_score += score

        # Normalize to sum to 1
        if total_score > 0:
            allocations = {k: v / total_score for k, v in allocations.items()}
        else:
            equal_weight = 1.0 / len(allocations) if allocations else 0.5
            allocations = {k: equal_weight for k in allocations}

        # Calculate expected return (simplified)
        expected_return = sum(
            allocations.get(p.get("symbol", ""), 0) * p.get("confidence", 50) / 100
            for p in predictions
        ) * 10  # Scale to percentage

        # Calculate risk score
        concentration = max(allocations.values()) if allocations else 0.5
        risk_score = min(concentration * 100, 100)

        state["allocations"] = allocations
        state["expected_return"] = round(expected_return, 2)
        state["risk_score"] = round(risk_score, 1)

        return state

    async def run(
        self,
        holdings: dict[str, float],
        predictions: list[dict[str, Any]],
        constraints: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run optimization pipeline."""
        state: OptimizerState = {
            "holdings": holdings,
            "predictions": predictions,
            "constraints": constraints,
            "analysis": None,
            "allocations": {},
            "expected_return": 0.0,
            "risk_score": 0.0,
        }

        state = await self.analyze_portfolio(state)
        state = await self.optimize(state)

        return {
            "allocations": state["allocations"],
            "expected_return": state["expected_return"],
            "risk_score": state["risk_score"],
            "analysis": state["analysis"],
        }
