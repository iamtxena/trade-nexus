---
title: Gate4 Risk Policy Controls
summary: Versioned risk policy contract with active pre-trade enforcement boundaries.
owners:
  - Team B
  - Team F
  - Team G
updated: 2026-02-15
---

# Gate4 Risk Policy Controls

## Objective

Define a machine-readable risk policy contract and enforce it before execution side effects, then halt runtime execution on drawdown breaches.

## Schema Contract

Schema artifact:

- `/contracts/schemas/risk-policy.v1.schema.json`

Required top-level fields:

- `version`
- `mode`
- `limits`
- `killSwitch`
- `actionsOnBreach`

## Validation Boundaries

1. Only schema version `risk-policy.v1` is accepted in this wave.
2. Unknown versions fail validation.
3. Invalid enums, malformed limits, and incompatible notional bounds fail validation.
4. Policy validation is deterministic and backed by contract tests.

## Active Pre-Trade Enforcement (AG-RISK-02)

Pre-trade checks are mandatory gates before side effects:

1. Deployment creation is blocked when policy limits would be exceeded.
2. Order placement is blocked on max-position/max-notional breaches.
3. Triggered kill-switch blocks deployment/order side effects.
4. Invalid or unsupported policy fails closed (no side effects).

## Active Drawdown Kill-Switch Runtime Handling (AG-RISK-03)

Runtime drawdown checks are enforced during deployment status refresh:

1. `latestPnl` is evaluated against deployment capital and `limits.maxDrawdownPct`.
2. Breach sets `killSwitch.triggered=true` with timestamp and breach reason.
3. Active deployments are sent to adapter stop flow immediately after breach detection.
4. Once triggered, pre-trade side-effecting commands remain blocked.

## Active Risk Audit Trail (AG-RISK-04)

Risk decisions now persist to runtime audit storage for both allow and block outcomes:

1. Pre-trade deployment and order checks record `approved`/`blocked` decisions.
2. Runtime drawdown checks record approval decisions and breach-triggered blocks.
3. Records include request identity (`request_id`, `tenant_id`, `user_id`), policy version/mode, and outcome code.
4. Invalid policy/version paths fail closed and emit blocked audit records.

## Risk Control Point Matrix

| Control Point | Behavior | Side-Effect Policy |
| --- | --- | --- |
| Deployment pre-trade check | Validate notional bounds + kill-switch state | Block on breach (`422/423`) before adapter call |
| Order pre-trade check | Validate symbol/portfolio notional, daily loss, reference price | Block on breach (`422/423`) before adapter call |
| Runtime drawdown monitor | Evaluate `latestPnl` vs drawdown limit | Trigger kill-switch and halt deployment path |
| Policy validation | Enforce schema/version compatibility | Fail closed on invalid policy (`500`) |

## Risk Decision and Audit Evidence Model

Audit entries capture deterministic decision metadata:

| Field | Description |
| --- | --- |
| `decision` | `approved` or `blocked` |
| `check_type` | Risk control category (`pretrade_deployment`, `pretrade_order`, `runtime_drawdown`) |
| `request_id` / `tenant_id` / `user_id` | Identity and correlation |
| `policy_version` / `policy_mode` | Evaluated policy context |
| `outcome_code` | Deterministic failure/signal code (`RISK_LIMIT_BREACH`, `RISK_KILL_SWITCH_ACTIVE`, etc.) |
| `reason` | Human-readable rationale |
| `metadata` | Structured context (notional, drawdown, symbol, deployment references) |

## Gate4 Scope Boundary

- AG-RISK-01 schema + validator, AG-RISK-02 pre-trade enforcement, AG-RISK-03 drawdown kill-switch handling, and AG-RISK-04 risk audit trail are active.

## Migration Notes

1. All new side-effecting execution paths must call risk gates before command dispatch.
2. Runtime additions should extend risk audit coverage rather than introducing non-audited checks.
3. Policy schema changes must be versioned and validated before rollout.

## Traceability

- Schema: `/contracts/schemas/risk-policy.v1.schema.json`
- Runtime validator: `/backend/src/platform_api/services/risk_policy.py`
- Pre-trade gate runtime: `/backend/src/platform_api/services/risk_pretrade_service.py`
- Drawdown kill-switch runtime: `/backend/src/platform_api/services/risk_killswitch_service.py`
- Risk audit runtime: `/backend/src/platform_api/services/risk_audit_service.py`
- Contract tests:
  - `/backend/tests/contracts/test_risk_policy_schema.py`
  - `/backend/tests/contracts/test_risk_pretrade_checks.py`
  - `/backend/tests/contracts/test_risk_killswitch_drawdown.py`
  - `/backend/tests/contracts/test_risk_audit_trail.py`
- Interface definition: `/docs/architecture/INTERFACES.md`
- Related epics/issues: `#77`, `#138`, `#106`
