# Validation Review Web Reviewer Workflow

Source: `docs/portal/platform/validation-reviewer-workflow.md`
Topic: `platform`
Stable ID: `portal_validation_reviewer_workflow_v1`

# Validation Review Web Reviewer Workflow

## Objective

Define the production flow for validation decisions, bot onboarding, and run-level sharing in the web lane, with optional API/CLI execution when needed.

## Guardrails

1. Contract-first: only use routes defined in `/docs/architecture/specs/platform-api.openapi.yaml`.
2. Platform API is the only client entrypoint for web, SDK, and optional CLI flows.
3. Identity is auth-derived; reviewer tooling must not treat raw tenant/user headers as trusted identity input.
4. JSON is canonical (`validation_run` artifact). HTML/PDF are optional derived outputs.
5. Shared access is run-level only and must route through the dedicated Shared Validation UX flow.
6. No client-side direct provider calls for this workflow surface.

## Web Flow (`/validation`)

1. Open `/validation` and authenticate through the dashboard session.
2. Create a run in the web form (owner user or owner bot context reflected through run actor metadata).
3. Confirm the proxy creates the run through `POST /api/validation/runs` -> `POST /v2/validation-runs`.
4. Load run status and canonical artifact:
   - `GET /api/validation/runs/{runId}`
   - `GET /api/validation/runs/{runId}/artifact`
5. Submit reviewer decision from the review form:
   - `POST /api/validation/runs/{runId}/review`
   - `POST /v2/validation-runs/{runId}/review`
   - required fields: `reviewerType`, `decision`
6. Request render output only when required for external distribution:
   - `POST /api/validation/runs/{runId}/render`
   - body `{"format":"html"}` or `{"format":"pdf"}`

## Bot Onboarding In Shared Validation Program

1. Invite-code registration path (`trial`, rate-limited):
   - `POST /v2/validation-bots/registrations/invite-code`
   - request fields: `inviteCode`, `botName`, optional `metadata`
2. Partner bootstrap registration path:
   - `POST /v2/validation-bots/registrations/partner-bootstrap`
   - request fields: `partnerKey`, `partnerSecret`, `ownerEmail`, `botName`, optional `metadata`
3. Both paths return:
   - `bot` (user-owned bot record)
   - `registration` audit record
   - `issuedKey` with one-time `rawKey`

## Key Lifecycle (Create, Show-Once, Rotate, Revoke)

1. Create:
   - initial bot registration response includes `issuedKey.rawKey`.
2. Show once:
   - raw key is returned only on create/rotate (`BotIssuedApiKey.rawKey`), never through metadata endpoints.
3. Rotate:
   - `POST /v2/validation-bots/{botId}/keys/rotate`
   - returns new `issuedKey.rawKey` and metadata.
4. Revoke:
   - `POST /v2/validation-bots/{botId}/keys/{keyId}/revoke`
   - returns key metadata with `status=revoked`.

## Actor Linkage Model (User vs Bot)

1. Validation run actor identity is explicit:
   - `ValidationRun.actor.actorType`: `user | bot`
   - `ValidationRun.actor.actorId` + optional `userId` and `botId`
2. Invite creator actor identity is explicit:
   - `ValidationInvite.invitedByActorType`: `user | bot`
3. Bot ownership remains user-bound (`ownerUserId`) with no brand entity in v1.

## Run-Level Invite Model And Permissions

1. Create invite by email:
   - `POST /v2/validation-sharing/runs/{runId}/invites`
   - required field: `email`
2. List invites for one run:
   - `GET /v2/validation-sharing/runs/{runId}/invites`
3. Revoke invite:
   - `POST /v2/validation-sharing/invites/{inviteId}/revoke`
4. Accept invite during login/session flow:
   - `POST /v2/validation-sharing/invites/{inviteId}/accept`
   - request includes `acceptedEmail`
5. Permission boundary:
   - canonical shared permission enum is `view | review`.
   - `view` grants shared read access only (`GET /v2/validation-sharing/runs/{runId}` and `/artifact`).
   - `review` grants shared read access plus shared write via `POST /v2/validation-sharing/runs/{runId}/review`.
   - owner-scoped invite management and run-share mutation stay owner-only.
6. Backward-compatibility note:
   - legacy alias permissions (`comment`, `decide`) normalize to `review`; newly authored docs and clients should only emit `view | review`.

## Dedicated Shared Validation UX Surface

1. Shared users enter through the Shared Validation reviewer flow (current web lane route `/validation`).
2. Shared run access is established only through invite acceptance path; no ambient cross-run access.
3. Shared users review canonical JSON first and request HTML/PDF only as derived outputs.
4. Shared review submissions must target `POST /v2/validation-sharing/runs/{runId}/review` (not owner-scoped `/v2/validation-runs/{runId}/review`).

## Deep-Link Flow (`#279`)

CLI and external tooling may open review-web directly with `runId` in query params:

- `/validation?runId=<runId>`

Workflow expectations:

1. Reviewer verifies the loaded run matches the CLI-provided `runId`.
2. Deep-link load uses existing read routes only:
   - `GET /v2/validation-runs/{runId}`
   - `GET /v2/validation-runs/{runId}/artifact`
3. If `runId` is absent, `/validation` falls back to manual run lookup without behavior change.

Operator notes:

1. No new Platform API route is introduced for deep-link support.
2. Deep-link failures do not bypass auth-derived identity controls.
3. Release evidence should include one successful deep-link open sample (`runId`, `requestId`, decision state).

## Optional API/CLI Lane

CLI output for `#279` can include a direct reviewer URL (`/validation?runId=<runId>`).
When running outside the CLI flow, use SDK or direct Platform API requests.

```bash
export API_BASE="https://api-nexus.lona.agency"
export TOKEN="<bearer-token>"
export REQUEST_ID="req-validation-review-$(date +%s)"
export IDEM_KEY="idem-validation-review-$(uuidgen | tr '[:upper:]' '[:lower:]')"

curl -sS "$API_BASE/v2/validation-runs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: $REQUEST_ID" \
  -H "Idempotency-Key: $IDEM_KEY" \
  -d '{
    "strategyId":"strat-001",
    "requestedIndicators":["zigzag","ema"],
    "datasetIds":["dataset-btc-1h-2025"],
    "backtestReportRef":"blob://validation/candidate/backtest-report.json",
    "policy":{
      "profile":"STANDARD",
      "blockMergeOnFail":true,
      "blockReleaseOnFail":true,
      "blockMergeOnAgentFail":true,
      "blockReleaseOnAgentFail":false,
      "requireTraderReview":true,
      "hardFailOnMissingIndicators":true,
      "failClosedOnEvidenceUnavailable":true
    }
  }'

export RUN_ID="<shared-run-id>"
export SHARED_REVIEW_IDEM_KEY="idem-shared-review-$(uuidgen | tr '[:upper:]' '[:lower:]')"

curl -sS "$API_BASE/v2/validation-sharing/runs/$RUN_ID/review" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: req-shared-review-$(date +%s)" \
  -H "Idempotency-Key: $SHARED_REVIEW_IDEM_KEY" \
  -d '{
    "reviewerType":"trader",
    "decision":"pass",
    "summary":"Shared review completed with no blocking findings."
  }'
```

## Reviewer Evidence Checklist

1. Record `runId`, `requestId`, and decision timestamp.
2. Save canonical artifact output from `GET /v2/validation-runs/{runId}/artifact`.
3. Save review submission request/response payloads.
4. Save render request/response payloads when HTML/PDF is requested.
5. Link governance checks from the PR:
   - `contracts-governance`
   - `docs-governance`
   - `llm-package-governance`

## PR and Program Status Updates

When opening and merging the PR for `#313`, post status updates in both the child issue and `#310`.

```md
Validation Review Web status:
- Parent: #310
- Child: #313
- PR: <url>
- Status: OPEN | IN_REVIEW | MERGED
- Checks: contracts-governance=<status>, docs-governance=<status>, llm-package-governance=<status>
- Cursor/Greptile findings: resolved | disposition linked
- Evidence: <CI run links + artifact refs>
```

## Traceability

- Child issue: [#313](https://github.com/iamtxena/trade-nexus/issues/313)
- Parent issue: [#310](https://github.com/iamtxena/trade-nexus/issues/310)
- Prior validation-review parent: [#288](https://github.com/iamtxena/trade-nexus/issues/288)
- Web lane page: `/frontend/src/app/(dashboard)/validation/page.tsx`
- Web API proxy: `/frontend/src/app/api/validation/runs/route.ts`
- Shared web API proxy: `/frontend/src/app/api/shared-validation/runs/`
- Contract source: `/docs/architecture/specs/platform-api.openapi.yaml`
- Governance: `/.github/workflows/contracts-governance.yml`, `/.github/workflows/docs-governance.yml`, `/.github/workflows/llm-package-governance.yml`
