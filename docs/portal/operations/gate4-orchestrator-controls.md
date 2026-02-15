---
title: Gate4 Orchestrator Controls
summary: Deterministic orchestrator state machine, queue/cancellation controls, and execution command boundary semantics.
owners:
  - Team B
  - Team F
  - Team G
updated: 2026-02-15
---

# Gate4 Orchestrator Controls

## Objective

Define a deterministic orchestrator lifecycle, queue/cancellation controls, retry/failure-budget policy, and execution command boundary so runtime behavior can be tested, audited, and safely hardened.

## State Contract

States:

- `received`
- `queued`
- `executing`
- `awaiting_tool`
- `awaiting_user_confirmation`
- `completed`
- `failed`
- `cancelled`

## Transition Boundaries

1. Requests start in `received` and move to `queued` before execution work begins.
2. Execution can pause only in `awaiting_tool` or `awaiting_user_confirmation`.
3. Terminal states are immutable: once `completed`, `failed`, or `cancelled`, no further transition is accepted.
4. Invalid transitions must fail deterministically with explicit errors.

## Deterministic Transition Matrix

| Current State | Allowed Targets |
| --- | --- |
| `received` | `received`, `queued`, `failed`, `cancelled` |
| `queued` | `queued`, `executing`, `failed`, `cancelled` |
| `executing` | `executing`, `awaiting_tool`, `awaiting_user_confirmation`, `completed`, `failed`, `cancelled` |
| `awaiting_tool` | `awaiting_tool`, `executing`, `failed`, `cancelled` |
| `awaiting_user_confirmation` | `awaiting_user_confirmation`, `executing`, `failed`, `cancelled` |
| `completed` | `completed` |
| `failed` | `failed` |
| `cancelled` | `cancelled` |

## Queue and Cancellation Controls (AG-ORCH-02)

Queue/cancellation runtime semantics are active:

1. Work items enter queue from `received -> queued`.
2. Queue scheduling is deterministic: lower numeric priority executes first; same priority is FIFO.
3. `dequeue` transitions `queued -> executing`.
4. Cancelling queued work prevents execution and records cancellation reason.
5. Cancelling executing/awaiting work transitions directly to `cancelled`.
6. Terminal states remain immutable under cancellation attempts.

## Retry and Failure Budget Policy (AG-ORCH-03)

Retry runtime semantics are deterministic and bounded:

1. Retry decisions are constrained by explicit `max_attempts` and `max_failures`.
2. Retry-eligible failures emit bounded exponential backoff delay metadata.
3. Retry path remains non-terminal and maps to retry-wait execution state (`awaiting_tool`).
4. Attempt/failure budget exhaustion emits terminal `failed` decision with deterministic reason codes.
5. Terminal retry states are immutable for further attempt scheduling.

### Retry Decision Matrix

| Condition | Decision | Next Runtime State |
| --- | --- | --- |
| Attempts and failures within budget | Retry allowed with bounded backoff | `awaiting_tool` |
| `max_attempts` exhausted | Retry denied | `failed` |
| `max_failures` exhausted | Retry denied | `failed` |
| Retry state already terminal | New attempts denied | `failed` (immutable) |

## Gate4 Scope Boundary

- AG-ORCH-01 transition contract, AG-ORCH-02 queue/cancellation controls, and AG-ORCH-03 retry/failure budget policy are active.

## Execution Command Boundary (AG-EXE-01)

Execution side-effect operations are routed through internal command handlers before adapter calls:

1. Deployment create/stop commands are emitted via command layer abstractions.
2. Order place/cancel commands are emitted via command layer abstractions.
3. Command layer delegates side effects to `ExecutionAdapter`; provider APIs remain adapter-only.
4. Read paths (list/get) remain non-command adapter reads.
5. Deployment create and order place commands enforce idempotency replay semantics; key/payload conflicts fail deterministically.

## Migration Notes

1. Runtime components should consume queue/retry outcomes via deterministic service calls, not ad-hoc state mutation.
2. New orchestrator features must extend contract tests before runtime behavior changes are merged.
3. Side-effecting execution retries remain gated by AG-RISK controls and execution command idempotency semantics.

## Traceability

- Architecture interface contract: `/docs/architecture/INTERFACES.md`
- Runtime implementation: `/backend/src/platform_api/services/orchestrator_state_machine.py`
- Queue/cancellation runtime: `/backend/src/platform_api/services/orchestrator_queue_service.py`
- Retry policy runtime: `/backend/src/platform_api/services/orchestrator_retry_policy.py`
- Execution command runtime: `/backend/src/platform_api/services/execution_command_service.py`
- Contract tests: `/backend/tests/contracts/test_orchestrator_state_machine.py`
- Contract tests: `/backend/tests/contracts/test_orchestrator_queue_cancellation.py`
- Contract tests: `/backend/tests/contracts/test_orchestrator_retry_policy.py`
- Contract tests: `/backend/tests/contracts/test_execution_command_layer.py`
- Contract tests: `/backend/tests/contracts/test_execution_command_idempotency.py`
- Related epics/issues: `#77`, `#138`, `#106`
