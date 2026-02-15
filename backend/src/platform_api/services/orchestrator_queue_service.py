"""Orchestrator queue, prioritization, and cancellation controls (AG-ORCH-02)."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from itertools import count
from typing import Any

from src.platform_api.services.orchestrator_state_machine import (
    INITIAL_ORCHESTRATOR_STATE,
    OrchestratorTransitionError,
    transition_state,
)
from src.platform_api.state_store import utc_now


@dataclass
class OrchestratorWorkItem:
    id: str
    priority: int
    state: str = INITIAL_ORCHESTRATOR_STATE
    payload: dict[str, Any] = field(default_factory=dict)
    cancellation_reason: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


class OrchestratorQueueService:
    """Deterministic queue with priority ordering and safe cancellation semantics."""

    def __init__(self) -> None:
        self._items: dict[str, OrchestratorWorkItem] = {}
        self._queue: list[tuple[int, int, str]] = []
        self._sequence = count(1)

    def enqueue(
        self,
        *,
        item_id: str,
        priority: int = 100,
        payload: dict[str, Any] | None = None,
    ) -> OrchestratorWorkItem:
        if item_id in self._items:
            raise ValueError(f"Orchestrator item already exists: {item_id}")

        item = OrchestratorWorkItem(
            id=item_id,
            priority=priority,
            payload=dict(payload or {}),
        )
        item.state = transition_state(item.state, "queued")
        item.updated_at = utc_now()
        self._items[item_id] = item
        heapq.heappush(self._queue, (priority, next(self._sequence), item_id))
        return item

    def dequeue_next(self) -> OrchestratorWorkItem | None:
        while self._queue:
            _, _, item_id = heapq.heappop(self._queue)
            item = self._items[item_id]
            if item.state != "queued":
                continue
            item.state = transition_state(item.state, "executing")
            item.updated_at = utc_now()
            return item
        return None

    def cancel(self, *, item_id: str, reason: str) -> OrchestratorWorkItem:
        item = self._require(item_id)
        item.state = transition_state(item.state, "cancelled")
        item.cancellation_reason = reason
        item.updated_at = utc_now()
        return item

    def mark_awaiting_tool(self, *, item_id: str) -> OrchestratorWorkItem:
        item = self._require(item_id)
        item.state = transition_state(item.state, "awaiting_tool")
        item.updated_at = utc_now()
        return item

    def mark_awaiting_user_confirmation(self, *, item_id: str) -> OrchestratorWorkItem:
        item = self._require(item_id)
        item.state = transition_state(item.state, "awaiting_user_confirmation")
        item.updated_at = utc_now()
        return item

    def resume(self, *, item_id: str) -> OrchestratorWorkItem:
        item = self._require(item_id)
        item.state = transition_state(item.state, "executing")
        item.updated_at = utc_now()
        return item

    def complete(self, *, item_id: str) -> OrchestratorWorkItem:
        item = self._require(item_id)
        item.state = transition_state(item.state, "completed")
        item.updated_at = utc_now()
        return item

    def fail(self, *, item_id: str) -> OrchestratorWorkItem:
        item = self._require(item_id)
        item.state = transition_state(item.state, "failed")
        item.updated_at = utc_now()
        return item

    def get(self, *, item_id: str) -> OrchestratorWorkItem:
        return self._require(item_id)

    def _require(self, item_id: str) -> OrchestratorWorkItem:
        item = self._items.get(item_id)
        if item is None:
            raise KeyError(f"Orchestrator item not found: {item_id}")
        return item


__all__ = [
    "OrchestratorQueueService",
    "OrchestratorTransitionError",
    "OrchestratorWorkItem",
]
