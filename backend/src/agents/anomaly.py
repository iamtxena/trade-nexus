"""Anomaly detection agent."""

from typing import Any, TypedDict

import numpy as np
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_xai import ChatXAI

from src.config import get_settings


class AnomalyState(TypedDict):
    """State for anomaly detection agent."""

    symbol: str
    data: list[float]
    analysis: str | None
    is_anomaly: bool
    score: float
    details: dict[str, Any] | None


class AnomalyAgent:
    """Agent for detecting market anomalies."""

    def __init__(self) -> None:
        settings = get_settings()
        self.llm = ChatXAI(
            model="grok-2-latest",
            api_key=settings.xai_api_key,
        )

    async def detect(self, state: AnomalyState) -> AnomalyState:
        """Detect anomalies using statistical methods."""
        data = np.array(state["data"])

        if len(data) < 3:
            state["is_anomaly"] = False
            state["score"] = 0.0
            state["details"] = {"error": "Insufficient data"}
            return state

        # Z-score based anomaly detection
        mean = np.mean(data)
        std = np.std(data)

        if std == 0:
            state["is_anomaly"] = False
            state["score"] = 0.0
            return state

        latest_value = data[-1]
        z_score = abs((latest_value - mean) / std)

        # Calculate anomaly score (0-1)
        score = min(z_score / 3.0, 1.0)  # Normalize to 0-1 range

        state["is_anomaly"] = z_score > 2.5
        state["score"] = float(score)
        state["details"] = {
            "z_score": float(z_score),
            "mean": float(mean),
            "std": float(std),
            "latest_value": float(latest_value),
            "threshold": 2.5,
        }

        return state

    async def analyze(self, state: AnomalyState) -> AnomalyState:
        """Analyze detected anomaly with LLM."""
        if not state["is_anomaly"]:
            state["analysis"] = "No significant anomaly detected."
            return state

        messages = [
            SystemMessage(
                content="""You are a market anomaly analysis agent. When an anomaly
                is detected, explain its potential causes and implications. Be concise."""
            ),
            HumanMessage(
                content=f"""Anomaly detected for {state['symbol']}:
                - Score: {state['score']:.2f}
                - Details: {state['details']}

                Explain the potential cause and trading implications."""
            ),
        ]

        response = await self.llm.ainvoke(messages)
        state["analysis"] = response.content

        if state["details"] is None:
            state["details"] = {}
        state["details"]["analysis"] = state["analysis"]

        return state

    async def run(self, symbol: str, data: list[float]) -> dict[str, Any]:
        """Run anomaly detection pipeline."""
        state: AnomalyState = {
            "symbol": symbol,
            "data": data,
            "analysis": None,
            "is_anomaly": False,
            "score": 0.0,
            "details": None,
        }

        state = await self.detect(state)
        state = await self.analyze(state)

        return {
            "is_anomaly": state["is_anomaly"],
            "score": state["score"],
            "details": state["details"],
        }
