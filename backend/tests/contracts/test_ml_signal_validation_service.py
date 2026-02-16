"""Contract tests for Gate5 ML signal validation and deterministic fallback."""

from __future__ import annotations

from src.platform_api.services.ml_signal_service import MLSignalValidationService


def test_ml_signal_validation_accepts_valid_payload() -> None:
    service = MLSignalValidationService()
    signals = service.validate(
        {
            "mlSignals": {
                "prediction": {"direction": "bullish", "confidence": 0.75},
                "sentiment": {"score": 0.64, "confidence": 0.61},
                "volatility": {"predictedPct": 38.0, "confidence": 0.7},
                "anomaly": {"isAnomaly": False, "score": 0.12, "confidence": 0.84},
                "regime": {"label": "risk_on", "confidence": 0.73},
            }
        }
    )
    assert signals.prediction_direction == "bullish"
    assert signals.regime_label == "risk_on"
    assert signals.regime_confidence == 0.73
    assert signals.used_fallback is False
    score = service.score_strategy(asset_class="crypto", idea_rank=0, signals=signals)
    assert 0.0 <= score <= 1.0
    assert "fallback=none" in service.summarize(signals=signals)


def test_ml_signal_validation_falls_back_when_payload_missing() -> None:
    service = MLSignalValidationService()
    signals = service.validate({})
    assert signals.prediction_direction == "neutral"
    assert signals.sentiment_score == 0.5
    assert signals.volatility_predicted_pct == 50.0
    assert signals.anomaly_flag is False
    assert signals.regime_label == "neutral"
    assert signals.used_fallback is True
    summary = service.summarize(signals=signals)
    assert "fallback=none" not in summary
    assert "ml_signals_missing" in summary


def test_ml_signal_validation_normalizes_out_of_range_values() -> None:
    service = MLSignalValidationService()
    signals = service.validate(
        {
            "mlSignals": {
                "prediction": {"direction": "sideways", "confidence": 180},
                "sentiment": {"score": 120, "confidence": -1},
                "volatility": {"predictedPct": -4, "confidence": 2},
                "anomaly": {"isAnomaly": "yes", "score": 2, "confidence": 200},
                "regime": {"label": "panic", "confidence": -4},
            }
        }
    )
    assert signals.prediction_direction == "neutral"
    assert signals.sentiment_score == 1.0
    assert signals.volatility_predicted_pct == 50.0
    assert signals.anomaly_score == 0.0
    assert signals.regime_label == "neutral"
    assert signals.used_fallback is True


def test_ml_signal_validation_clamps_high_sentiment_percentages() -> None:
    service = MLSignalValidationService()
    signals = service.validate(
        {
            "mlSignals": {
                "prediction": {"direction": "bullish", "confidence": 0.8},
                "sentiment": {"score": 240, "confidence": 0.9},
                "volatility": {"predictedPct": 25.0, "confidence": 0.7},
                "anomaly": {"isAnomaly": False, "score": 0.1, "confidence": 0.8},
                "regime": {"label": "risk_on", "confidence": 0.9},
            }
        }
    )

    assert signals.sentiment_score == 1.0
    assert "sentiment_score_clamped" in signals.fallback_reasons


def test_ml_signal_validation_flags_anomaly_breach_state() -> None:
    service = MLSignalValidationService()
    signals = service.validate(
        {
            "mlSignals": {
                "prediction": {"direction": "neutral", "confidence": 0.7},
                "sentiment": {"score": 0.5, "confidence": 0.6},
                "volatility": {"predictedPct": 70, "confidence": 0.8},
                "anomaly": {"isAnomaly": True, "score": 0.92, "confidence": 0.88},
                "regime": {"label": "risk_off", "confidence": 0.82},
            }
        }
    )

    assert signals.anomaly_breach_active is True
    assert signals.regime_label == "risk_off"
    assert signals.regime_confidence == 0.82
    assert "anomaly=breach" in service.summarize(signals=signals)


def test_ml_signal_validation_treats_boolean_confidence_as_missing() -> None:
    service = MLSignalValidationService()
    signals = service.validate(
        {
            "mlSignals": {
                "prediction": {"direction": "neutral", "confidence": 0.7},
                "sentiment": {"score": 0.5, "confidence": 0.6},
                "volatility": {"predictedPct": 70, "confidence": 0.8},
                "anomaly": {"isAnomaly": True, "score": 0.92, "confidence": True},
                "regime": {"label": "risk_off", "confidence": True},
            }
        }
    )

    assert signals.anomaly_confidence == 0.0
    assert signals.regime_confidence == 0.0
    assert signals.regime_label == "neutral"
    assert signals.anomaly_breach_active is False
    assert "anomaly_confidence_missing" in signals.fallback_reasons
    assert "regime_confidence_missing" in signals.fallback_reasons
