"""Contract tests for KB ingestion pipeline behavior."""

from src.platform_api.knowledge.ingestion import KnowledgeIngestionPipeline
from src.platform_api.state_store import InMemoryStateStore


def test_backtest_ingestion_is_idempotent_for_same_payload() -> None:
    store = InMemoryStateStore()
    pipeline = KnowledgeIngestionPipeline(store)
    strategy = store.strategies["strat-001"]
    backtest = store.backtests["bt-001"]

    pipeline.ingest_backtest_outcome(strategy=strategy, backtest=backtest)
    pipeline.ingest_backtest_outcome(strategy=strategy, backtest=backtest)

    assert len(store.lessons_learned) == 1


def test_deployment_ingestion_is_idempotent_for_same_state() -> None:
    store = InMemoryStateStore()
    pipeline = KnowledgeIngestionPipeline(store)
    deployment = store.deployments["dep-001"]

    pipeline.ingest_deployment_outcome(deployment)
    pipeline.ingest_deployment_outcome(deployment)

    assert len(store.lessons_learned) == 1
