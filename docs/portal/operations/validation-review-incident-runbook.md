---
title: Validation Review Incident Runbook
summary: Operator incident procedures for validation render failures, auth failures, and replay-regression failures.
owners:
  - Validation Review Web Docs
  - Team F
updated: 2026-02-20
---

# Validation Review Incident Runbook

## Objective

Provide deterministic incident handling for the validation review web program across the three blocking failure classes in scope for `#282`.

## Incident Class A: Render Failures (`/render`)

### Trigger

`POST /v2/validation-runs/{runId}/render` returns repeated failures or render jobs remain non-completing.

### Triage Commands

```bash
RUN_ID="<run-id>"
TOKEN="<bearer-token>"
API_BASE="https://api-nexus.lona.agency"

curl -sS "$API_BASE/v2/validation-runs/$RUN_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Request-Id: req-validation-render-status-001"

curl -sS "$API_BASE/v2/validation-runs/$RUN_ID/artifact" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Request-Id: req-validation-render-artifact-001"
```

### Containment And Recovery

1. Keep JSON artifact workflow active; do not block reviewer decision on HTML/PDF.
2. Re-submit render request with a fresh `Idempotency-Key`.
3. Capture request/response payloads and backend logs in the issue evidence comment.

## Incident Class B: Auth Failures (`401`)

### Trigger

Web proxy or direct API calls return `401 Unauthorized` during run creation/review/render retrieval.

### Triage Commands

```bash
TOKEN="<bearer-token>"
API_BASE="https://api-nexus.lona.agency"

curl -i "$API_BASE/v2/validation-runs/nonexistent" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Request-Id: req-validation-auth-check-001"

curl -i "$API_BASE/v1/health"
```

### Containment And Recovery

1. Re-authenticate the reviewer session and retry via `/validation`.
2. Verify proxy auth resolution behavior in `/frontend/src/lib/validation/server/auth.ts`.
3. Confirm identity scope is auth-derived and no caller-supplied tenant/user override path is being used.

## Incident Class C: Regression Replay Failures (`/validation-regressions/replay`)

### Trigger

Replay response returns gate-blocking decision (`mergeGateStatus=blocked` or `releaseGateStatus=blocked`), or policy checks fail.

### Triage Commands

```bash
pytest backend/tests/contracts/test_validation_replay_policy.py
pytest backend/tests/contracts/test_validation_release_gate_check.py
PYTHONPATH=backend python -m src.platform_api.validation.release_gate_check
```

### Containment And Recovery

1. Freeze merge/release progression for the candidate change.
2. Compare baseline and candidate evidence references from replay payload.
3. Patch deterministic or policy drift, rerun contract/replay tests, and re-run replay.

## Incident Class D: Deep-Link Run Load Failures (`#279`)

### Trigger

Reviewer opens `/validation?runId=<runId>` but run detail/artifact does not resolve in web UI.

### Triage Commands

```bash
RUN_ID="<run-id>"
TOKEN="<bearer-token>"
API_BASE="https://api-nexus.lona.agency"

curl -sS "$API_BASE/v2/validation-runs/$RUN_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Request-Id: req-validation-deeplink-run-001"

curl -sS "$API_BASE/v2/validation-runs/$RUN_ID/artifact" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Request-Id: req-validation-deeplink-artifact-001"
```

### Containment And Recovery

1. Verify the deep link contains the exact `runId` returned by CLI/SDK output.
2. If API calls pass, reload `/validation?runId=<runId>` with a fresh authenticated session.
3. If API calls fail, treat as contract/auth incident and follow Class B/C flow.

## Governance And Review Findings Disposition

1. Resolve Cursor and Greptile findings before merge when a fix is feasible in-scope.
2. If a finding is intentionally deferred, post explicit disposition in the PR thread with rationale, owner, and follow-up issue.
3. Keep review threads resolved before merge (`review-governance`).

## Evidence Capture Template

Use this template in child issue `#282` and mirror summary in parent `#288`.

```md
Validation Review incident update:
- Parent: #288
- Child: #282
- Incident class: render_failure | auth_failure | regression_failure
- Run ID / Replay ID: <id>
- Request IDs: <list>
- Impact: <scope + user effect>
- Containment: <actions completed>
- Recovery: <actions completed>
- CI checks: contracts-governance=<status>, docs-governance=<status>, llm-package-governance=<status>
- Cursor/Greptile findings: resolved | disposition linked
- Evidence links: <logs, artifacts, workflow runs, PR>
```

## Traceability

- Child issue: [#282](https://github.com/iamtxena/trade-nexus/issues/282)
- Related deep-link issue: [#279](https://github.com/iamtxena/trade-nexus/issues/279)
- Parent issue: [#288](https://github.com/iamtxena/trade-nexus/issues/288)
- Contract source: `/docs/architecture/specs/platform-api.openapi.yaml`
- Replay gate check: `/backend/src/platform_api/validation/release_gate_check.py`
- Contract tests: `/backend/tests/contracts/test_validation_replay_policy.py`
- Governance workflows: `/.github/workflows/contracts-governance.yml`, `/.github/workflows/docs-governance.yml`, `/.github/workflows/llm-package-governance.yml`
