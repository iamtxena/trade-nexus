"""Canonical Knowledge Base v1.0 schema records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.platform_api.state_store import utc_now

KB_SCHEMA_VERSION = "1.0"


@dataclass
class KnowledgePatternRecord:
    id: str
    name: str
    pattern_type: str
    description: str
    suitable_regimes: list[str]
    assets: list[str]
    timeframes: list[str]
    confidence_score: float
    source_ref: str | None = None
    schema_version: str = KB_SCHEMA_VERSION
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class MarketRegimeRecord:
    id: str
    asset: str
    regime: str
    volatility: str
    indicators: dict[str, float] = field(default_factory=dict)
    start_at: str = field(default_factory=utc_now)
    end_at: str | None = None
    notes: str | None = None
    schema_version: str = KB_SCHEMA_VERSION
    created_at: str = field(default_factory=utc_now)


@dataclass
class LessonLearnedRecord:
    id: str
    lesson: str
    category: str
    tags: list[str]
    strategy_id: str | None = None
    backtest_id: str | None = None
    deployment_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = KB_SCHEMA_VERSION
    created_at: str = field(default_factory=utc_now)


@dataclass
class MacroEventRecord:
    id: str
    title: str
    summary: str
    impact: str
    occurred_at: str
    assets: list[str] = field(default_factory=list)
    source_url: str | None = None
    schema_version: str = KB_SCHEMA_VERSION
    created_at: str = field(default_factory=utc_now)


@dataclass
class CorrelationEdgeRecord:
    id: str
    source_asset: str
    target_asset: str
    correlation: float
    window: str
    computed_at: str = field(default_factory=utc_now)
    schema_version: str = KB_SCHEMA_VERSION
