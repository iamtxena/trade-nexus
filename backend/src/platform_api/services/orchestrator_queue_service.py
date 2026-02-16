"""Orchestrator queue, prioritization, and cancellation controls (AG-ORCH-02)."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from itertools import count
from typing import Any

from src.platform_api.services.orchestrator_trace_service import (
    OrchestratorTraceIdentity,
    OrchestratorTraceService,
)
from src.platform_api.services.orchestrator_state_machine import (
    INITIAL_ORCHESTRATOR_STATE,
    OrchestratorTransitionError,
    transition_state,
)
from src.platform_api.state_store import InMemoryStateStore
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

    def __init__(
        self,
        *,
        store: InMemoryStateStore | None = None,
        trace_service: OrchestratorTraceService | None = None,
        trace_identity: OrchestratorTraceIdentity | None = None,
    ) -> None:
        self._items: dict[str, OrchestratorWorkItem] = {}
        self._queue: list[tuple[int, int, str]] = []
        self._sequence = count(1)
        self._trace_service = trace_service or (OrchestratorTraceService(store=store) if store is not None else None)
        self._trace_identity = trace_identity

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
        self._record_trace(
            run_id=item_id,
            event="run_received",
            step="enqueue",
            from_state=None,
            to_state=item.state,
            metadata={"priority": priority},
        )
        previous_state = item.state
        item.state = transition_state(item.state, "queued")
        item.updated_at = utc_now()
        self._record_trace(
            run_id=item_id,
            event="state_transition",
            step="enqueue",
            from_state=previous_state,
            to_state=item.state,
            metadata={"priority": priority},
        )
        self._items[item_id] = item
        heapq.heappush(self._queue, (priority, next(self._sequence), item_id))
        return item

    def dequeue_next(self) -> OrchestratorWorkItem | None:
        while self._queue:
            _, _, item_id = heapq.heappop(self._queue)
            item = self._items[item_id]
            if item.state != "queued":
                continue
            previous_state = item.state
            item.state = transition_state(item.state, "executing")
            item.updated_at = utc_now()
            self._record_trace(
                run_id=item.id,
                event="state_transition",
                step="dequeue",
                from_state=previous_state,
                to_state=item.state,
            )
            return item
        return None

    def cancel(self, *, item_id: str, reason: str) -> OrchestratorWorkItem:
        item = self._require(item_id)
        previous_state = item.state
        item.state = transition_state(item.state, "cancelled")
        item.cancellation_reason = reason
        item.updated_at = utc_now()
        self._record_trace(
            run_id=item.id,
            event="state_transition",
            step="cancel",
            from_state=previous_state,
            to_state=item.state,
            metadata={"reason": reason},
        )
        return item

    def mark_awaiting_tool(self, *, item_id: str) -> OrchestratorWorkItem:
        item = self._require(item_id)
        previous_state = item.state
        item.state = transition_state(item.state, "awaiting_tool")
        item.updated_at = utc_now()
        self._record_trace(
            run_id=item.id,
            event="state_transition",
            step="await_tool",
            from_state=previous_state,
            to_state=item.state,
        )
        return item

    def mark_awaiting_user_confirmation(self, *, item_id: str) -> OrchestratorWorkItem:
        item = self._require(item_id)
        previous_state = item.state
        item.state = transition_state(item.state, "awaiting_user_confirmation")
        item.updated_at = utc_now()
        self._record_trace(
            run_id=item.id,
            event="state_transition",
            step="await_user_confirmation",
            from_state=previous_state,
            to_state=item.state,
        )
        return item

    def resume(self, *, item_id: str) -> OrchestratorWorkItem:
        item = self._require(item_id)
        previous_state = item.state
        item.state = transition_state(item.state, "executing")
        item.updated_at = utc_now()
        self._record_trace(
            run_id=item.id,
            event="state_transition",
            step="resume",
            from_state=previous_state,
            to_state=item.state,
        )
        return item

    def complete(self, *, item_id: str) -> OrchestratorWorkItem:
        item = self._require(item_id)
        previous_state = item.state
        item.state = transition_state(item.state, "completed")
        item.updated_at = utc_now()
        self._record_trace(
            run_id=item.id,
            event="state_transition",
            step="complete",
            from_state=previous_state,
            to_state=item.state,
        )
        return item

    def fail(self, *, item_id: str) -> OrchestratorWorkItem:
        item = self._require(item_id)
        previous_state = item.state
        item.state = transition_state(item.state, "failed")
        item.updated_at = utc_now()
        self._record_trace(
            run_id=item.id,
            event="state_transition",
            step="fail",
            from_state=previous_state,
            to_state=item.state,
        )
        return item

    def get(self, *, item_id: str) -> OrchestratorWorkItem:
        return self._require(item_id)

    def _require(self, item_id: str) -> OrchestratorWorkItem:
        item = self._items.get(item_id)
        if item is None:
            raise KeyError(f"Orchestrator item not found: {item_id}")
        return item

    def _record_trace(
        self,
        *,
        run_id: str,
        event: str,
        step: str,
        from_state: str | None,
        to_state: str | None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        if self._trace_service is None:
            return
        self._trace_service.record(
            run_id=run_id,
            event=event,
            step=step,
            from_state=from_state,
            to_state=to_state,
            identity=self._trace_identity,
            metadata=metadata,
        )


__all__ = [
    "OrchestratorQueueService",
    "OrchestratorTransitionError",
    "OrchestratorWorkItem",
]
