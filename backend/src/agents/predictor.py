"""Predictor agent for price/trend forecasting."""

from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_xai import ChatXAI

from src.config import get_settings
from src.models.lstm import LSTMPredictor


class PredictorState(TypedDict):
    """State for predictor agent."""

    symbol: str
    prediction_type: str
    timeframe: str
    features: dict[str, float] | None
    analysis: str | None
    prediction: dict[str, Any] | None
    confidence: float


class PredictorAgent:
    """Agent for generating price/trend predictions."""

    def __init__(self) -> None:
        settings = get_settings()
        self.llm = ChatXAI(
            model="grok-2-latest",
            api_key=settings.xai_api_key,
        )
        self.predictor = LSTMPredictor()

    async def analyze(self, state: PredictorState) -> PredictorState:
        """Analyze market conditions."""
        messages = [
            SystemMessage(
                content="""You are a market analysis agent. Analyze the given market
                conditions and provide insights for prediction. Focus on:
                - Current market trends
                - Key indicators
                - Risk factors"""
            ),
            HumanMessage(
                content=f"""Analyze market conditions for {state['symbol']}:
                - Prediction type: {state['prediction_type']}
                - Timeframe: {state['timeframe']}
                - Features: {state.get('features', {})}"""
            ),
        ]

        response = await self.llm.ainvoke(messages)
        state["analysis"] = response.content
        return state

    async def predict(self, state: PredictorState) -> PredictorState:
        """Generate prediction using ML model."""
        # Use LSTM model for prediction
        features = state.get("features") or {}

        prediction = self.predictor.predict(
            symbol=state["symbol"],
            prediction_type=state["prediction_type"],
            timeframe=state["timeframe"],
            features=features,
        )

        state["prediction"] = prediction
        state["confidence"] = prediction.get("confidence", 50.0)
        return state

    async def run(
        self,
        symbol: str,
        prediction_type: str,
        timeframe: str,
        features: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Run full prediction pipeline."""
        state: PredictorState = {
            "symbol": symbol,
            "prediction_type": prediction_type,
            "timeframe": timeframe,
            "features": features,
            "analysis": None,
            "prediction": None,
            "confidence": 0.0,
        }

        state = await self.analyze(state)
        state = await self.predict(state)

        return {
            "value": state["prediction"],
            "confidence": state["confidence"],
            "analysis": state["analysis"],
        }
