# Validation Review Web Reviewer Workflow

Source: `docs/portal/platform/validation-reviewer-workflow.md`
Topic: `platform`
Stable ID: `portal_validation_reviewer_workflow_v1`

# Validation Review Web Reviewer Workflow

## Objective

Define the production reviewer flow for validation decisions in the web lane, with optional API/CLI execution when needed.

## Guardrails

1. Contract-first: only use routes defined in `/docs/architecture/specs/platform-api.openapi.yaml`.
2. Platform API is the only client entrypoint for web, SDK, and optional CLI flows.
3. Identity is auth-derived; reviewer tooling must not treat raw tenant/user headers as trusted identity input.
4. JSON is canonical (`validation_run` artifact). HTML/PDF are optional derived outputs.

## Web Flow (`/validation`)

1. Open `/validation` and authenticate through the dashboard session.
2. Create a run in the web form.
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

When opening and merging the PR for `#282`, post status updates in both the child issue and `#288`.

```md
Validation Review Web status:
- Parent: #288
- Child: #282
- PR: <url>
- Status: OPEN | IN_REVIEW | MERGED
- Checks: contracts-governance=<status>, docs-governance=<status>, llm-package-governance=<status>
- Cursor/Greptile findings: resolved | disposition linked
- Evidence: <CI run links + artifact refs>
```

## Traceability

- Child issue: [#282](https://github.com/iamtxena/trade-nexus/issues/282)
- Parent issue: [#288](https://github.com/iamtxena/trade-nexus/issues/288)
- Web lane page: `/frontend/src/app/(dashboard)/validation/page.tsx`
- Web API proxy: `/frontend/src/app/api/validation/runs/route.ts`
- Contract source: `/docs/architecture/specs/platform-api.openapi.yaml`
- Governance: `/.github/workflows/contracts-governance.yml`, `/.github/workflows/docs-governance.yml`, `/.github/workflows/llm-package-governance.yml`
