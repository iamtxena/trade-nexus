# Gate5 Structured Observability Fields

Source: `docs/portal/operations/gate5-structured-observability.md`
Topic: `operations`
Stable ID: `portal_gate5_structured_observability_v1`

# Gate5 Structured Observability Fields

## Objective

Make runtime logs queryable by request and actor identity so release stabilization and incident response can trace execution paths deterministically.

## Required Structured Fields

All Platform API request/service logs emit:

1. `requestId`
2. `tenantId`
3. `userId`
4. `component`
5. `operation`
6. `resourceType` (when applicable)
7. `resourceId` (when applicable)

## Runtime Coverage

Structured observability is emitted across:

1. request middleware (`request_started`, `request_completed`, unhandled failure path),
2. research (`market_scan` enrichment events),
3. risk pretrade decisions (`approved`/`blocked`),
4. execution command orchestration (`create_deployment`, `create_order`),
5. reconciliation drift checks,
6. conversation session/turn lifecycle.

## Validation Evidence

Contract coverage asserts correlation fields are present and consistent:

- `/backend/tests/contracts/test_observability_structured_fields.py`
- `/backend/tests/contracts/test_error_envelope_runtime.py`

## Traceability

- Runtime helper: `/backend/src/platform_api/observability.py`
- Middleware entrypoint: `/backend/src/main.py`
- Interface contract: `/docs/architecture/INTERFACES.md`
- Related issues: `#42`, `#81`, `#106`
