"""Validation and deterministic scoring helpers for optional ML signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_ALLOWED_PREDICTION_DIRECTIONS = {"bullish", "bearish", "neutral"}
_ALLOWED_REGIME_LABELS = {"risk_on", "neutral", "risk_off"}
_REGIME_ALIASES = {
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
_REGIME_CONFIDENCE_MIN = 0.55
_ANOMALY_BREACH_SCORE = 0.8
_ANOMALY_BREACH_CONFIDENCE = 0.7


def _clamp(value: float, *, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


@dataclass(frozen=True)
class ValidatedMLSignals:
    prediction_direction: str
    prediction_confidence: float
    sentiment_score: float
    sentiment_confidence: float
    volatility_predicted_pct: float
    volatility_confidence: float
    anomaly_score: float
    anomaly_flag: bool
    anomaly_confidence: float
    regime_label: str
    regime_confidence: float
    fallback_reasons: tuple[str, ...] = ()

    @property
    def used_fallback(self) -> bool:
        return len(self.fallback_reasons) > 0

    @property
    def anomaly_breach_active(self) -> bool:
        return (
            self.anomaly_flag
            and self.anomaly_score >= _ANOMALY_BREACH_SCORE
            and self.anomaly_confidence >= _ANOMALY_BREACH_CONFIDENCE
        )


class MLSignalValidationService:
    """Normalizes optional model outputs and emits deterministic fallback metadata."""

    def validate(self, context_payload: dict[str, object]) -> ValidatedMLSignals:
        fallback_reasons: list[str] = []
        raw_ml = context_payload.get("mlSignals")
        if not isinstance(raw_ml, dict):
            fallback_reasons.append("ml_signals_missing")
            raw_ml = {}

        raw_prediction = raw_ml.get("prediction")
        raw_sentiment = raw_ml.get("sentiment")
        raw_volatility = raw_ml.get("volatility")
        raw_anomaly = raw_ml.get("anomaly")
        raw_regime = raw_ml.get("regime")

        prediction_direction = self._prediction_direction(raw_prediction, fallback_reasons)
        prediction_confidence = self._normalized_confidence(raw_prediction, fallback_reasons, source="prediction")
        sentiment_score = self._normalized_score(raw_sentiment, fallback_reasons, source="sentiment")
        sentiment_confidence = self._normalized_confidence(raw_sentiment, fallback_reasons, source="sentiment")
        volatility_predicted_pct = self._volatility_pct(raw_volatility, fallback_reasons)
        volatility_confidence = self._normalized_confidence(raw_volatility, fallback_reasons, source="volatility")
        anomaly_score = self._normalized_score(raw_anomaly, fallback_reasons, source="anomaly")
        anomaly_flag = self._anomaly_flag(raw_anomaly, fallback_reasons)
        anomaly_confidence = self._normalized_confidence(raw_anomaly, fallback_reasons, source="anomaly")
        regime_label = self._regime_label(raw_regime, fallback_reasons)
        regime_confidence = self._normalized_confidence(raw_regime, fallback_reasons, source="regime")
        if regime_confidence < _REGIME_CONFIDENCE_MIN:
            fallback_reasons.append("regime_confidence_low")
            regime_label = "neutral"

        return ValidatedMLSignals(
            prediction_direction=prediction_direction,
            prediction_confidence=prediction_confidence,
            sentiment_score=sentiment_score,
            sentiment_confidence=sentiment_confidence,
            volatility_predicted_pct=volatility_predicted_pct,
            volatility_confidence=volatility_confidence,
            anomaly_score=anomaly_score,
            anomaly_flag=anomaly_flag,
            anomaly_confidence=anomaly_confidence,
            regime_label=regime_label,
            regime_confidence=regime_confidence,
            fallback_reasons=tuple(dict.fromkeys(fallback_reasons)),
        )

    def score_strategy(
        self,
        *,
        asset_class: str,
        idea_rank: int,
        signals: ValidatedMLSignals,
    ) -> float:
        base_score = _clamp(0.64 - (idea_rank * 0.05), minimum=0.2, maximum=0.8)
        direction_bias = {
            "bullish": 0.10,
            "bearish": -0.10,
            "neutral": 0.0,
        }[signals.prediction_direction]
        sentiment_bias = (signals.sentiment_score - 0.5) * 0.25
        volatility_penalty = max(signals.volatility_predicted_pct - 60.0, 0.0) * 0.002
        regime_bias = {
            "risk_on": 0.04,
            "neutral": 0.0,
            "risk_off": -0.12,
        }[signals.regime_label]
        anomaly_penalty = 0.0
        if signals.anomaly_confidence >= _REGIME_CONFIDENCE_MIN:
            anomaly_penalty = (0.15 if signals.anomaly_flag else 0.0) + (signals.anomaly_score * 0.12)
        if signals.anomaly_breach_active:
            anomaly_penalty += 0.2
        asset_bonus = 0.03 if asset_class.lower() == "crypto" else 0.0

        score = base_score + direction_bias + sentiment_bias + regime_bias + asset_bonus - volatility_penalty - anomaly_penalty
        return _clamp(score, minimum=0.0, maximum=1.0)

    def summarize(self, *, signals: ValidatedMLSignals) -> str:
        fallback = "none" if not signals.used_fallback else ",".join(signals.fallback_reasons)
        anomaly_label = "breach" if signals.anomaly_breach_active else ("active" if signals.anomaly_flag else "clear")
        return (
            "ML signal validation:"
            f" prediction={signals.prediction_direction}:{signals.prediction_confidence:.2f};"
            f" sentiment={signals.sentiment_score:.2f}:{signals.sentiment_confidence:.2f};"
            f" volatility={signals.volatility_predicted_pct:.1f}%:{signals.volatility_confidence:.2f};"
            f" anomaly={anomaly_label}:{signals.anomaly_score:.2f}:{signals.anomaly_confidence:.2f};"
            f" regime={signals.regime_label}:{signals.regime_confidence:.2f};"
            f" fallback={fallback}"
        )

    @staticmethod
    def _prediction_direction(payload: object, fallback_reasons: list[str]) -> str:
        if not isinstance(payload, dict):
            fallback_reasons.append("prediction_missing")
            return "neutral"
        raw_direction = payload.get("direction")
        if not isinstance(raw_direction, str):
            fallback_reasons.append("prediction_direction_missing")
            return "neutral"
        normalized = raw_direction.strip().lower()
        if normalized not in _ALLOWED_PREDICTION_DIRECTIONS:
            fallback_reasons.append("prediction_direction_invalid")
            return "neutral"
        return normalized

    @staticmethod
    def _normalized_confidence(payload: object, fallback_reasons: list[str], *, source: str) -> float:
        if not isinstance(payload, dict):
            fallback_reasons.append(f"{source}_confidence_missing")
            return 0.0
        raw = payload.get("confidence")
        if not isinstance(raw, (int, float)):
            fallback_reasons.append(f"{source}_confidence_missing")
            return 0.0
        numeric = float(raw)
        if numeric > 1.0:
            numeric = numeric / 100.0
        if numeric < 0.0 or numeric > 1.0:
            fallback_reasons.append(f"{source}_confidence_out_of_range")
            return 0.0
        return _clamp(numeric, minimum=0.0, maximum=1.0)

    @staticmethod
    def _normalized_score(payload: object, fallback_reasons: list[str], *, source: str) -> float:
        if not isinstance(payload, dict):
            fallback_reasons.append(f"{source}_score_missing")
            return 0.5 if source == "sentiment" else 0.0
        raw = payload.get("score")
        if not isinstance(raw, (int, float)):
            fallback_reasons.append(f"{source}_score_missing")
            return 0.5 if source == "sentiment" else 0.0
        numeric = float(raw)
        if source == "sentiment" and numeric > 1.0:
            numeric = numeric / 100.0
            if numeric > 1.0:
                fallback_reasons.append("sentiment_score_clamped")
                numeric = 1.0
        if numeric < 0.0 or numeric > 1.0:
            fallback_reasons.append(f"{source}_score_out_of_range")
            return 0.5 if source == "sentiment" else 0.0
        return _clamp(numeric, minimum=0.0, maximum=1.0)

    @staticmethod
    def _volatility_pct(payload: object, fallback_reasons: list[str]) -> float:
        if not isinstance(payload, dict):
            fallback_reasons.append("volatility_missing")
            return 50.0
        raw = payload.get("predictedPct")
        if not isinstance(raw, (int, float)):
            fallback_reasons.append("volatility_predicted_pct_missing")
            return 50.0
        numeric = float(raw)
        if numeric < 0.0:
            fallback_reasons.append("volatility_predicted_pct_negative")
            return 50.0
        return _clamp(numeric, minimum=0.0, maximum=500.0)

    @staticmethod
    def _anomaly_flag(payload: object, fallback_reasons: list[str]) -> bool:
        if not isinstance(payload, dict):
            fallback_reasons.append("anomaly_missing")
            return False
        raw = payload.get("isAnomaly")
        if isinstance(raw, bool):
            return raw
        fallback_reasons.append("anomaly_flag_missing")
        return False

    @staticmethod
    def _regime_label(payload: object, fallback_reasons: list[str]) -> str:
        if not isinstance(payload, dict):
            fallback_reasons.append("regime_missing")
            return "neutral"
        raw = payload.get("label")
        if not isinstance(raw, str):
            raw = payload.get("regime")
        if not isinstance(raw, str):
            raw = payload.get("state")
        if not isinstance(raw, str):
            fallback_reasons.append("regime_label_missing")
            return "neutral"

        normalized = raw.strip().lower()
        if normalized == "":
            fallback_reasons.append("regime_label_missing")
            return "neutral"

        mapped = _REGIME_ALIASES.get(normalized, normalized.replace(" ", "_"))
        if mapped not in _ALLOWED_REGIME_LABELS:
            fallback_reasons.append("regime_label_invalid")
            return "neutral"
        return mapped
