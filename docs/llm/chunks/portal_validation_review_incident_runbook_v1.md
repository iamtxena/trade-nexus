# Validation Review Incident Runbook

Source: `docs/portal/operations/validation-review-incident-runbook.md`
Topic: `operations`
Stable ID: `portal_validation_review_incident_runbook_v1`

# Validation Review Incident Runbook

## Objective

Provide deterministic incident handling for the validation review web program across bot identity, run-level sharing, and replay gate failure classes in scope for `#283`.

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

## Incident Class E: Invite-Code Rate Limit And Registration Failures

### Trigger

`POST /v2/validation-bots/registrations/invite-code` returns `429` or repeated create failures for trial onboarding.

### Expected Contract Behavior

1. Invite-code path is rate-limited and may return `429`.
2. Partner bootstrap path is a separate onboarding path (`POST /v2/validation-bots/registrations/partner-bootstrap`).
3. Both registration writes require `Idempotency-Key` and return `201` on success.

### Triage Commands

```bash
API_BASE="https://api-nexus.lona.agency"
REQUEST_ID="req-val-bot-reg-$(date +%s)"
IDEM_KEY="idem-val-bot-reg-$(uuidgen | tr '[:upper:]' '[:lower:]')"

curl -i -sS "$API_BASE/v2/validation-bots/registrations/invite-code" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: $REQUEST_ID" \
  -H "Idempotency-Key: $IDEM_KEY" \
  -d '{
    "inviteCode":"INV-TRIAL-REDACTED",
    "botName":"Validation Bot Placeholder"
  }'
```

### Containment And Recovery

1. Preserve canonical request/response artifacts (`requestId`, `error.code`, `error.message`).
2. Retry only with same payload/idempotency intent; do not mutate payload under same key.
3. If trial rate limit persists and bootstrap credentials are available, switch to partner bootstrap path.

## Incident Class F: Invite Acceptance Flow Failures

### Trigger

`POST /v2/validation-sharing/invites/{inviteId}/accept` fails or returns conflict/not-found states during Shared Validation login flow.

### Expected Contract Behavior

1. Acceptance requires `acceptedEmail` in `AcceptValidationInviteRequest`.
2. Success returns both updated `invite` and granted `share` payload.
3. Invite lifecycle states: `pending`, `accepted`, `revoked`, `expired`.

### Triage Commands

```bash
API_BASE="https://api-nexus.lona.agency"
TOKEN="<bearer-token>"
INVITE_ID="<invite-id>"
REQUEST_ID="req-val-invite-accept-$(date +%s)"
IDEM_KEY="idem-val-invite-accept-$(uuidgen | tr '[:upper:]' '[:lower:]')"

curl -i -sS "$API_BASE/v2/validation-sharing/invites/$INVITE_ID/accept" \
  -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: $REQUEST_ID" \
  -H "Idempotency-Key: $IDEM_KEY" \
  -d '{
    "acceptedEmail":"reviewer@example.com",
    "loginSessionId":"sess-placeholder"
  }'
```

### Common Failure Cases

1. `400`: malformed request payload (missing/invalid `acceptedEmail`).
2. `401`: missing/expired auth session.
3. `404`: invite not found.
4. `409`: invite no longer actionable (`accepted`, `revoked`, `expired`) or conflicting share state.

### Containment And Recovery

1. Verify accepted email exactly matches invite email target.
2. Confirm invite status using `GET /v2/validation-sharing/runs/{runId}/invites`.
3. Reissue invite when state is `revoked`/`expired` and review must proceed.

## Secret Handling And Key Rotation Playbook

### Rules

1. Never log, commit, or screenshot raw bot keys (`issuedKey.rawKey`).
2. Treat raw key as write-once secret; retain only key metadata (`id`, `keyPrefix`, `status`) in operational logs.
3. Use rotation (`/v2/validation-bots/{botId}/keys/rotate`) for planned rollover.
4. Use revocation (`/v2/validation-bots/{botId}/keys/{keyId}/revoke`) for compromise containment.

### Rotation Procedure

1. Rotate key and capture response metadata (`requestId`, `botId`, `issuedKey.key.id`, `keyPrefix`).
2. Distribute new raw key through approved secret manager channel only.
3. Validate downstream auth with the new key.
4. Revoke superseded key once cutover is confirmed.

### Compromise Procedure

1. Immediately revoke compromised key ID.
2. Rotate to issue replacement key.
3. Audit `lastUsedAt`, request IDs, and affected run/share actions.
4. Post incident summary with mitigation and follow-up tasks.

## Governance And Review Findings Disposition

1. Resolve Cursor and Greptile findings before merge when a fix is feasible in-scope.
2. If a finding is intentionally deferred, post explicit disposition in the PR thread with rationale, owner, and follow-up issue.
3. Keep review threads resolved before merge (`review-governance`).

## Evidence Capture Template

Use this template in child issue `#313` and mirror summary in parent `#310`.

```md
Validation Review incident update:
- Parent: #310
- Child: #313
- Incident class: render_failure | auth_failure | regression_failure | invite_rate_limit | invite_acceptance | key_compromise
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

- Child issue: [#313](https://github.com/iamtxena/trade-nexus/issues/313)
- Related deep-link issue: [#279](https://github.com/iamtxena/trade-nexus/issues/279)
- Parent issue: [#310](https://github.com/iamtxena/trade-nexus/issues/310)
- Prior validation-review parent: [#288](https://github.com/iamtxena/trade-nexus/issues/288)
- Contract source: `/docs/architecture/specs/platform-api.openapi.yaml`
- Replay gate check: `/backend/src/platform_api/validation/release_gate_check.py`
- Contract tests: `/backend/tests/contracts/test_validation_replay_policy.py`
- Governance workflows: `/.github/workflows/contracts-governance.yml`, `/.github/workflows/docs-governance.yml`, `/.github/workflows/llm-package-governance.yml`
