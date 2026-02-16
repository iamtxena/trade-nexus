# Gate5 Release Runbooks And Client Validation

Source: `docs/portal/operations/gate5-release-runbooks-and-client-validation.md`
Topic: `operations`
Stable ID: `portal_gate5_release_runbooks_client_validation_v1`

# Gate5 Release Runbooks And Client Validation

## Objective

Define one operational playbook for Gate5 release validation and incident handling across CLI, Web, OpenClaw, and agent-runtime client lanes.

## Entry Criteria

Run this playbook only when foundational dependencies are complete:

1. `#44` consumer-driven mock contract checks merged.
2. `#45` SLO and alert baseline merged.
3. `#75` deployment profile reconciled to one active path.
4. `#80` pre-release readiness dependency is either:
   - closed, or
   - explicitly waived with rationale and approver reference recorded on `#150`.

## Release Validation Sequence

1. Confirm required governance checks are green on release PRs:
   - `contract-governance`
   - `review-governance`
   - `docs-governance`
   - `llm-package-governance`
2. Confirm deployment profile remains singular:
   - `/docs/portal/operations/gate5-deployment-profile.md`
3. Confirm reliability closure evidence is current:
   - `/docs/portal/operations/gate5-reliability-deployment-closure.md`
4. Execute lane-by-lane compatibility checks (below).

## Cross-Client Compatibility Matrix

| Lane | Validation Surface | Primary Commands | Pass Criteria |
| --- | --- | --- | --- |
| CLI | Platform boundary + mock consumer checks | `cd trading-cli && bun run ci` | contract tests pass, no boundary drift |
| Web | OpenAPI + SDK contract compatibility | `cd trade-nexus && bash contracts/scripts/verify-sdk-drift.sh` | SDK in sync with OpenAPI contract |
| OpenClaw | Platform API lane contract + end-to-end flow | `cd trade-nexus/backend && uv run --with pytest python -m pytest tests/contracts/test_openclaw_client_lane_contract.py tests/contracts/test_openclaw_e2e_flow.py` | both suites pass |
| Agent runtime | risk/research/reconciliation/orchestrator contracts | `cd trade-nexus/backend && uv run --with pytest python -m pytest tests/contracts` | full contract suite passes |

## Deployment Promotion And Rollback

Promotion and rollback follow the existing operational runbooks:

1. Promotion guide: `/.ops/runbooks/release-promotion.md`
2. Smoke validation: `/.ops/scripts/smoke-check.sh`
3. Rollback automation: `/.ops/scripts/rollback.sh`
4. SLO reference: `/.ops/runbooks/slo-definitions.md`

## Incident Handling Playbook

### Scenario A: Contract Regression

1. Contain: block merge and hold deployment promotion.
2. Verify with:
   - `pytest backend/tests/contracts/test_openapi_contract_baseline.py`
   - `pytest backend/tests/contracts/test_openapi_contract_freeze.py`
   - `bash contracts/scripts/check-breaking-changes.sh`
3. Recover: patch contract/runtime mismatch, rerun gates, and repost evidence on the release issue.

### Scenario B: Reliability/SLO Breach

1. Contain: halt release progression, run smoke checks, and assess active revision health.
2. Verify with:
   - `/.ops/scripts/smoke-check.sh`
   - SLO baseline at `contracts/config/slo-alert-baseline.v1.json`
3. Recover: execute rollback (`/.ops/scripts/rollback.sh`) if breach criteria are met.

### Scenario C: Cross-Client Compatibility Failure

1. Contain: freeze release and identify affected lane(s).
2. Reproduce using lane-specific commands from the compatibility matrix.
3. Recover: fix contract drift or client expectation mismatch, then rerun lane and governance checks.

## Evidence Recording

For each release candidate, capture:

1. CI run URLs for required governance checks.
2. Command output summaries per lane.
3. Deployment revision and smoke-check outcome.
4. Any rollback/incident actions executed.

Use:

- `/.ops/templates/release-evidence.md`
- `/.ops/templates/drill-report.md`

## Traceability

- Child issue: `#147`
- Parent epics: `#81`, `#106`
- Signoff: `#150`
- Related docs:
  - `/docs/portal/operations/gate5-deployment-profile.md`
  - `/docs/portal/operations/gate5-reliability-deployment-closure.md`
  - `/docs/portal/operations/gate5-consumer-mock-contracts.md`
  - `/docs/portal/operations/gate5-slo-alerting-baseline.md`
