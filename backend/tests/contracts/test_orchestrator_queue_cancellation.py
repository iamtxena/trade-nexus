"""Contract tests for AG-ORCH-02 queue prioritization and cancellation semantics."""

from __future__ import annotations

import pytest

from src.platform_api.services.orchestrator_queue_service import (
    OrchestratorQueueService,
    OrchestratorTransitionError,
)


def test_priority_queue_dequeues_highest_priority_first() -> None:
    service = OrchestratorQueueService()

    service.enqueue(item_id="orch-low", priority=50)
    service.enqueue(item_id="orch-high", priority=10)
    service.enqueue(item_id="orch-mid", priority=20)

    first = service.dequeue_next()
    second = service.dequeue_next()
    third = service.dequeue_next()

    assert first is not None and first.id == "orch-high"
    assert second is not None and second.id == "orch-mid"
    assert third is not None and third.id == "orch-low"
    assert service.dequeue_next() is None


def test_fifo_order_for_same_priority() -> None:
    service = OrchestratorQueueService()

    service.enqueue(item_id="orch-a", priority=20)
    service.enqueue(item_id="orch-b", priority=20)
    service.enqueue(item_id="orch-c", priority=20)

    assert service.dequeue_next().id == "orch-a"  # type: ignore[union-attr]
    assert service.dequeue_next().id == "orch-b"  # type: ignore[union-attr]
    assert service.dequeue_next().id == "orch-c"  # type: ignore[union-attr]


def test_cancelling_queued_item_prevents_execution() -> None:
    service = OrchestratorQueueService()

    service.enqueue(item_id="orch-queued", priority=5)
    cancelled = service.cancel(item_id="orch-queued", reason="superseded")
    assert cancelled.state == "cancelled"
    assert cancelled.cancellation_reason == "superseded"
    assert service.dequeue_next() is None


def test_cancelling_executing_item_is_allowed() -> None:
    service = OrchestratorQueueService()

    service.enqueue(item_id="orch-exec", priority=5)
    executing = service.dequeue_next()
    assert executing is not None and executing.state == "executing"

    cancelled = service.cancel(item_id="orch-exec", reason="manual override")
    assert cancelled.state == "cancelled"
    assert cancelled.cancellation_reason == "manual override"


def test_terminal_item_cannot_be_cancelled() -> None:
    service = OrchestratorQueueService()

    service.enqueue(item_id="orch-done", priority=10)
    service.dequeue_next()
    service.complete(item_id="orch-done")

    with pytest.raises(OrchestratorTransitionError):
        service.cancel(item_id="orch-done", reason="should fail")


def test_queue_skips_cancelled_items_and_continues() -> None:
    service = OrchestratorQueueService()

    service.enqueue(item_id="orch-a", priority=10)
    service.enqueue(item_id="orch-b", priority=20)
    service.cancel(item_id="orch-a", reason="duplicate")

    next_item = service.dequeue_next()
    assert next_item is not None
    assert next_item.id == "orch-b"
