"""Orchestrator execution trace persistence for lifecycle and step transitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from src.platform_api.state_store import InMemoryStateStore, OrchestratorExecutionTraceRecord


@dataclass(frozen=True)
class OrchestratorTraceIdentity:
    request_id: str = "system-orchestrator"
    tenant_id: str = "tenant-local"
    user_id: str = "user-local"


class OrchestratorTraceService:
    """Persists deterministic orchestrator execution trace records."""

    def __init__(self, *, store: InMemoryStateStore) -> None:
        self._store = store

    def record(
        self,
        *,
        run_id: str,
        event: str,
        step: str,
        from_state: str | None,
        to_state: str | None,
        identity: OrchestratorTraceIdentity | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> OrchestratorExecutionTraceRecord:
        actor = identity or OrchestratorTraceIdentity()
        trace = OrchestratorExecutionTraceRecord(
            id=self._store.next_id("orchestrator_trace"),
            run_id=run_id,
            event=event,
            step=step,
            from_state=from_state,
            to_state=to_state,
            request_id=actor.request_id,
            tenant_id=actor.tenant_id,
            user_id=actor.user_id,
            metadata=dict(metadata or {}),
        )
        self._store.orchestrator_execution_traces.append(trace)
        return trace

    def list_run_traces(self, *, run_id: str) -> list[OrchestratorExecutionTraceRecord]:
        return [trace for trace in self._store.orchestrator_execution_traces if trace.run_id == run_id]

