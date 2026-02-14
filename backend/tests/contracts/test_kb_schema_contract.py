"""Contract tests for canonical Knowledge Base schema v1.0."""

from __future__ import annotations

from src.platform_api.knowledge.models import (
    KB_SCHEMA_VERSION,
    CorrelationEdgeRecord,
    KnowledgePatternRecord,
    LessonLearnedRecord,
    MacroEventRecord,
    MarketRegimeRecord,
)


def test_knowledge_pattern_schema_defaults() -> None:
    record = KnowledgePatternRecord(
        id="kbp-0001",
        name="Momentum Baseline",
        pattern_type="momentum",
        description="Trend-following setup for risk-on regimes.",
        suitable_regimes=["bull"],
        assets=["BTCUSDT"],
        timeframes=["1h"],
        confidence_score=0.7,
    )
    assert record.schema_version == KB_SCHEMA_VERSION
    assert record.confidence_score >= 0
    assert record.confidence_score <= 1


def test_market_regime_schema_defaults() -> None:
    record = MarketRegimeRecord(
        id="kbr-0001",
        asset="BTCUSDT",
        regime="sideways",
        volatility="medium",
        indicators={"rsi": 50.0},
    )
    assert record.schema_version == KB_SCHEMA_VERSION
    assert record.end_at is None


def test_lesson_macro_and_correlation_records_include_schema_version() -> None:
    lesson = LessonLearnedRecord(
        id="kbl-0001",
        lesson="Keep position size lower during chop.",
        category="risk_sizing",
        tags=["risk", "sizing"],
    )
    event = MacroEventRecord(
        id="kbe-0001",
        title="CPI release",
        summary="Inflation came above consensus.",
        impact="high",
    )
    edge = CorrelationEdgeRecord(
        id="kbc-0001",
        source_asset="BTCUSDT",
        target_asset="ETHUSDT",
        correlation=0.81,
        window="30d",
    )
    assert lesson.schema_version == KB_SCHEMA_VERSION
    assert event.schema_version == KB_SCHEMA_VERSION
    assert edge.schema_version == KB_SCHEMA_VERSION
