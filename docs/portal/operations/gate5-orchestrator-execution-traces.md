---
title: Gate5 Orchestrator Execution Traces
summary: Append-only orchestrator lifecycle and retry trace contract for runtime auditability.
owners:
  - Team F
  - Team G
updated: 2026-02-16
---

# Gate5 Orchestrator Execution Traces

## Objective

Persist deterministic orchestrator traces for run lifecycle transitions and retry decisions so runtime behavior is auditable.

## Runtime Contract

1. State store record type: `OrchestratorExecutionTraceRecord`.
2. Storage location: `InMemoryStateStore.orchestrator_execution_traces`.
3. Trace identity fields are required on every record:
   - `request_id`
   - `tenant_id`
   - `user_id`
4. Trace records are append-only and chronological for each `run_id`.

## Emitted Events

### Queue lifecycle

- `run_received`
- `state_transition`

Transitions covered by step labels:

- `enqueue`
- `dequeue`
- `await_tool`
- `await_user_confirmation`
- `resume`
- `cancel`
- `complete`
- `fail`

### Retry policy

- `retry_attempt_started`
- `retry_failure_recorded`
- `retry_scheduled`
- `retry_terminal_decision`
- `retry_success`

## Validation Coverage

Contract tests verify:

1. Lifecycle state transitions are traced end-to-end.
2. Retry schedule and terminal decisions are traced with metadata.
3. Trace identity propagation is preserved for auditability.

Relevant tests:

- `backend/tests/contracts/test_orchestrator_execution_traces.py`
- `backend/tests/contracts/test_orchestrator_queue_cancellation.py`
- `backend/tests/contracts/test_orchestrator_retry_policy.py`

## Traceability

- Child issue: `#49`
- Parent epics: `#77`, `#81`
- Interface contract: `docs/architecture/INTERFACES.md`

