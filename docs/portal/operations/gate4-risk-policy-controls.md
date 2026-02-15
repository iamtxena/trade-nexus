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

Define a machine-readable risk policy contract and enforce it before execution side effects.

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

## Gate4 Scope Boundary

- AG-RISK-01 schema + validator and AG-RISK-02 pre-trade enforcement are active.
- Drawdown kill-switch runtime handling is in AG-RISK-03 (`#56`).
- Risk audit trail is in AG-RISK-04 (`#57`).

## Traceability

- Schema: `/contracts/schemas/risk-policy.v1.schema.json`
- Runtime validator: `/backend/src/platform_api/services/risk_policy.py`
- Pre-trade gate runtime: `/backend/src/platform_api/services/risk_pretrade_service.py`
- Contract tests:
  - `/backend/tests/contracts/test_risk_policy_schema.py`
  - `/backend/tests/contracts/test_risk_pretrade_checks.py`
- Interface definition: `/docs/architecture/INTERFACES.md`
- Related epics/issues: `#77`, `#138`, `#106`
