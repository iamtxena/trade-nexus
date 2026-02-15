---
title: Gate4 Risk Policy Controls
summary: Versioned risk policy schema contract and validation boundaries for runtime controls.
owners:
  - Team B
  - Team F
  - Team G
updated: 2026-02-14
---

# Gate4 Risk Policy Controls

## Objective

Define a machine-readable risk policy contract that runtime components can validate before any pre-trade enforcement work in follow-up issues.

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

## Gate4 Scope Boundary

- This issue defines schema + validator only.
- Pre-trade enforcement is in AG-RISK-02 (`#55`).
- Drawdown kill-switch runtime handling is in AG-RISK-03 (`#56`).
- Risk audit trail is in AG-RISK-04 (`#57`).

## Traceability

- Schema: `/contracts/schemas/risk-policy.v1.schema.json`
- Runtime validator: `/backend/src/platform_api/services/risk_policy.py`
- Contract tests: `/backend/tests/contracts/test_risk_policy_schema.py`
- Interface definition: `/docs/architecture/INTERFACES.md`
- Related epics/issues: `#77`, `#138`, `#106`
