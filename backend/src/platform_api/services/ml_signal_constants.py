"""Shared constants for ML signal validation and risk gating behavior."""

from __future__ import annotations

REGIME_ALIASES: dict[str, str] = {
    "risk_on": "risk_on",
    "risk-on": "risk_on",
    "bullish": "risk_on",
    "uptrend": "risk_on",
    "neutral": "neutral",
    "sideways": "neutral",
    "range": "neutral",
    "risk_off": "risk_off",
    "risk-off": "risk_off",
    "bearish": "risk_off",
    "downtrend": "risk_off",
}

REGIME_CONFIDENCE_MIN = 0.55
ANOMALY_BREACH_SCORE = 0.8
ANOMALY_BREACH_CONFIDENCE = 0.7
ML_SIGNAL_MARKET_KEY = "__market__"
