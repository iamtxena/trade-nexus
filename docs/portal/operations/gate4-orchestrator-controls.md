---
title: Gate4 Orchestrator Controls
summary: Deterministic orchestrator state machine and execution command boundary semantics.
owners:
  - Team B
  - Team F
  - Team G
updated: 2026-02-14
---

# Gate4 Orchestrator Controls

## Objective

Define a deterministic orchestrator lifecycle and execution command boundary so runtime behavior can be tested, audited, and safely hardened in follow-up issues.

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

## Gate4 Scope Boundary

- This contract defines transitions only.
- Queue/cancellation runtime processing lands in AG-ORCH-02 (`#47`).
- Retry and failure budget policy lands in AG-ORCH-03 (`#48`).

## Execution Command Boundary (AG-EXE-01)

Execution side-effect operations are routed through internal command handlers before adapter calls:

1. Deployment create/stop commands are emitted via command layer abstractions.
2. Order place/cancel commands are emitted via command layer abstractions.
3. Command layer delegates side effects to `ExecutionAdapter`; provider APIs remain adapter-only.
4. Read paths (list/get) remain non-command adapter reads.
5. Deployment create and order place commands enforce idempotency replay semantics; key/payload conflicts fail deterministically.

## Traceability

- Architecture interface contract: `/docs/architecture/INTERFACES.md`
- Runtime implementation: `/backend/src/platform_api/services/orchestrator_state_machine.py`
- Execution command runtime: `/backend/src/platform_api/services/execution_command_service.py`
- Contract tests: `/backend/tests/contracts/test_orchestrator_state_machine.py`
- Contract tests: `/backend/tests/contracts/test_execution_command_layer.py`
- Contract tests: `/backend/tests/contracts/test_execution_command_idempotency.py`
- Related epics/issues: `#77`, `#138`, `#106`
