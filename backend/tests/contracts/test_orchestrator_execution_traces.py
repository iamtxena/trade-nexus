"""Contract tests for AG-ORCH-04 orchestrator execution trace persistence."""

from __future__ import annotations

from src.platform_api.services.orchestrator_queue_service import OrchestratorQueueService
from src.platform_api.services.orchestrator_retry_policy import (
    OrchestratorRetryPolicyService,
    RetryBudgetPolicy,
)
from src.platform_api.services.orchestrator_trace_service import OrchestratorTraceIdentity
from src.platform_api.state_store import InMemoryStateStore


def test_queue_lifecycle_transitions_persist_execution_traces() -> None:
    store = InMemoryStateStore()
    queue = OrchestratorQueueService(store=store)

    queue.enqueue(item_id="orch-trace-001", priority=7, payload={"scope": "dataset"})
    queue.dequeue_next()
    queue.mark_awaiting_tool(item_id="orch-trace-001")
    queue.resume(item_id="orch-trace-001")
    queue.mark_awaiting_user_confirmation(item_id="orch-trace-001")
    queue.resume(item_id="orch-trace-001")
    queue.complete(item_id="orch-trace-001")

    traces = [trace for trace in store.orchestrator_execution_traces if trace.run_id == "orch-trace-001"]
    assert [trace.event for trace in traces] == [
        "run_received",
        "state_transition",
        "state_transition",
        "state_transition",
        "state_transition",
        "state_transition",
        "state_transition",
        "state_transition",
    ]
    assert [trace.step for trace in traces] == [
        "enqueue",
        "enqueue",
        "dequeue",
        "await_tool",
        "resume",
        "await_user_confirmation",
        "resume",
        "complete",
    ]
    assert [(trace.from_state, trace.to_state) for trace in traces] == [
        (None, "received"),
        ("received", "queued"),
        ("queued", "executing"),
        ("executing", "awaiting_tool"),
        ("awaiting_tool", "executing"),
        ("executing", "awaiting_user_confirmation"),
        ("awaiting_user_confirmation", "executing"),
        ("executing", "completed"),
    ]
    assert all(trace.id.startswith("orch-trace-") for trace in traces)
    assert all(trace.request_id == "system-orchestrator" for trace in traces)
    assert all(trace.tenant_id == "tenant-local" for trace in traces)
    assert all(trace.user_id == "user-local" for trace in traces)


def test_retry_decisions_emit_trace_records_for_retry_schedule_and_terminal_failure() -> None:
    store = InMemoryStateStore()
    retry = OrchestratorRetryPolicyService(
        store=store,
        policy=RetryBudgetPolicy(
            max_attempts=2,
            max_failures=2,
            base_backoff_seconds=1,
            max_backoff_seconds=30,
        ),
    )

    retry.begin_attempt(item_id="orch-retry-001")
    first = retry.record_failure(item_id="orch-retry-001")
    assert first.retry_allowed is True

    retry.begin_attempt(item_id="orch-retry-001")
    second = retry.record_failure(item_id="orch-retry-001")
    assert second.retry_allowed is False
    assert second.reason == "attempt_budget_exhausted"

    traces = [trace for trace in store.orchestrator_execution_traces if trace.run_id == "orch-retry-001"]
    assert [trace.event for trace in traces] == [
        "retry_attempt_started",
        "retry_failure_recorded",
        "retry_scheduled",
        "retry_attempt_started",
        "retry_failure_recorded",
        "retry_terminal_decision",
    ]
    terminal = traces[-1]
    assert terminal.to_state == "failed"
    assert terminal.metadata["reason"] == "attempt_budget_exhausted"


def test_trace_identity_is_propagated_for_auditability() -> None:
    store = InMemoryStateStore()
    identity = OrchestratorTraceIdentity(
        request_id="req-orch-trace-001",
        tenant_id="tenant-trace",
        user_id="user-trace",
    )
    queue = OrchestratorQueueService(store=store, trace_identity=identity)

    queue.enqueue(item_id="orch-trace-identity", priority=10)
    queue.cancel(item_id="orch-trace-identity", reason="manual_abort")

    traces = [trace for trace in store.orchestrator_execution_traces if trace.run_id == "orch-trace-identity"]
    assert len(traces) == 3
    assert all(trace.request_id == "req-orch-trace-001" for trace in traces)
    assert all(trace.tenant_id == "tenant-trace" for trace in traces)
    assert all(trace.user_id == "user-trace" for trace in traces)
    assert traces[-1].metadata["reason"] == "manual_abort"


def test_retry_terminal_trace_after_success_preserves_completed_reason() -> None:
    store = InMemoryStateStore()
    retry = OrchestratorRetryPolicyService(store=store)

    retry.begin_attempt(item_id="orch-retry-success-001")
    retry.record_success(item_id="orch-retry-success-001")
    decision = retry.record_failure(item_id="orch-retry-success-001")

    assert decision.next_state == "completed"
    assert decision.reason == "retry_succeeded"

    traces = [trace for trace in store.orchestrator_execution_traces if trace.run_id == "orch-retry-success-001"]
    assert [trace.event for trace in traces] == [
        "retry_attempt_started",
        "retry_success",
        "retry_terminal_decision",
    ]
    terminal_trace = traces[-1]
    assert terminal_trace.to_state == "completed"
    assert terminal_trace.metadata["reason"] == "retry_succeeded"
