"""Knowledge Base ingestion pipeline with idempotent upserts."""

from __future__ import annotations

from src.platform_api.knowledge.models import (
    KB_SCHEMA_VERSION,
    CorrelationEdgeRecord,
    KnowledgePatternRecord,
    LessonLearnedRecord,
    MacroEventRecord,
    MarketRegimeRecord,
)
from src.platform_api.state_store import BacktestRecord, DeploymentRecord, InMemoryStateStore, StrategyRecord, utc_now


class KnowledgeIngestionPipeline:
    """Idempotent writes from runtime events into Knowledge Base records."""

    def __init__(self, store: InMemoryStateStore) -> None:
        self._store = store

    def seed_defaults(self) -> None:
        if self._store.knowledge_patterns:
            return

        pattern_id = self._store.next_id("knowledge_pattern")
        self._store.knowledge_patterns[pattern_id] = KnowledgePatternRecord(
            id=pattern_id,
            name="Mean Reversion Baseline",
            pattern_type="mean_reversion",
            description="Reversion strategy for range-bound markets with volatility filters.",
            suitable_regimes=["sideways", "low_volatility"],
            assets=["BTCUSDT", "ETHUSDT"],
            timeframes=["1h", "4h"],
            confidence_score=0.64,
            source_ref="seed",
            schema_version=KB_SCHEMA_VERSION,
        )

        regime_id = self._store.next_id("knowledge_regime")
        self._store.market_regimes[regime_id] = MarketRegimeRecord(
            id=regime_id,
            asset="BTCUSDT",
            regime="sideways",
            volatility="medium",
            indicators={"rsi": 49.5, "atr_pct": 2.3},
            notes="Seed regime for Gate3 baseline.",
        )

    def upsert_pattern(self, pattern: KnowledgePatternRecord) -> None:
        pattern.updated_at = utc_now()
        self._store.knowledge_patterns[pattern.id] = pattern

    def upsert_regime(self, regime: MarketRegimeRecord) -> None:
        self._store.market_regimes[regime.id] = regime

    def upsert_macro_event(self, event: MacroEventRecord) -> None:
        self._store.macro_events[event.id] = event

    def upsert_correlation(self, edge: CorrelationEdgeRecord) -> None:
        self._store.correlations[edge.id] = edge

    def ingest_backtest_outcome(
        self,
        *,
        strategy: StrategyRecord | None,
        backtest: BacktestRecord,
    ) -> None:
        fingerprint = self._store.payload_fingerprint(
            {
                "scope": "backtest_outcome",
                "strategy_id": strategy.id if strategy is not None else None,
                "backtest_id": backtest.id,
                "status": backtest.status,
                "metrics": backtest.metrics,
                "error": backtest.error,
            }
        )
        if fingerprint in self._store.knowledge_ingestion_events:
            return
        self._store.knowledge_ingestion_events.add(fingerprint)

        lesson_id = self._store.next_id("knowledge_lesson")
        if backtest.status == "completed":
            lesson = f"Backtest {backtest.id} completed with Sharpe {backtest.metrics.get('sharpeRatio', 0):.2f}."
            category = "backtest_completed"
        else:
            lesson = f"Backtest {backtest.id} ended with status {backtest.status}."
            category = "backtest_failure" if backtest.status == "failed" else "backtest_status"

        self._store.lessons_learned[lesson_id] = LessonLearnedRecord(
            id=lesson_id,
            lesson=lesson,
            category=category,
            tags=[backtest.status, "backtest"],
            strategy_id=strategy.id if strategy is not None else None,
            backtest_id=backtest.id,
            metadata={"metrics": backtest.metrics, "error": backtest.error},
        )

    def ingest_deployment_outcome(self, deployment: DeploymentRecord) -> None:
        fingerprint = self._store.payload_fingerprint(
            {
                "scope": "deployment_outcome",
                "deployment_id": deployment.id,
                "status": deployment.status,
                "latest_pnl": deployment.latest_pnl,
            }
        )
        if fingerprint in self._store.knowledge_ingestion_events:
            return
        self._store.knowledge_ingestion_events.add(fingerprint)

        lesson_id = self._store.next_id("knowledge_lesson")
        summary = (
            f"Deployment {deployment.id} status={deployment.status} latestPnl={deployment.latest_pnl}"
            if deployment.latest_pnl is not None
            else f"Deployment {deployment.id} status={deployment.status}"
        )
        self._store.lessons_learned[lesson_id] = LessonLearnedRecord(
            id=lesson_id,
            lesson=summary,
            category="deployment_state",
            tags=["deployment", deployment.status],
            deployment_id=deployment.id,
            strategy_id=deployment.strategy_id,
        )
