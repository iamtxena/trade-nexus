---
title: Platform API Contract
summary: Integration entrypoint and contract rules for Platform API consumers.
owners:
  - Gate1 Docs Team
updated: 2026-02-20
---

# Platform API Contract

## Canonical Contract Source

- `/docs/architecture/specs/platform-api.openapi.yaml`

All public API behavior, request/response schemas, and examples are governed by this file.

## Consumer Rules

1. Integrations must use generated SDK artifacts where available.
2. Endpoint usage must map to OpenAPI-defined `operationId`s.
3. Breaking changes require architecture approval and major-version strategy.

## Validation Contract Note (`#280`)

For validation artifacts returned by `/v2/validation-runs/{runId}/artifact`:

1. `agentReview.budget` is part of the canonical contract payload.
2. Budget includes profile limits, usage, and `withinBudget` decision metadata.
3. Client integrations should treat this field as required when parsing `validation_run` artifacts.
4. Operator triage for budget-related failures should use contract tests before runtime retries:
   - `pytest backend/tests/contracts/test_validation_schema_contract.py`
   - `pytest backend/tests/contracts/test_openapi_contract_v2_validation_freeze.py`

## Supporting Docs

- `/docs/architecture/INTERFACES.md`
- `/docs/architecture/API_CONTRACT_GOVERNANCE.md`
- `/docs/architecture/specs/SDK_RELEASE.md`
- `/docs/architecture/specs/MOCK_SERVER.md`
