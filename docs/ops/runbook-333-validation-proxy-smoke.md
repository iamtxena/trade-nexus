# Runbook: Credentialed Validation Proxy Smoke (Issue #333)

| Field | Value |
|-------|-------|
| Issue | #333 (follow-up to #325) |
| Owner | CloudOps |
| Service | `trade-nexus` frontend web proxy |
| Coverage | `POST /api/validation/runs`, `GET /api/validation/runs/{runId}`, `GET /api/validation/runs/{runId}/artifact` |

## Purpose

Provide a repeatable, non-interactive smoke that validates authenticated traffic through the **web proxy routes** (not direct backend routes), while keeping credentials out of repository history and logs.

## CI Entrypoint

- Workflow: `.github/workflows/validation-proxy-smoke.yml`
- Trigger: `workflow_dispatch` (manual run)
- Script: `.ops/scripts/validation-proxy-smoke.py`
- Artifacts per run:
  - `validation-proxy-smoke-<run-stamp>.json`
  - `validation-proxy-smoke-<run-stamp>.tsv`
  - `validation-proxy-smoke-<run-stamp>.txt`

## Required Secrets

Set these in GitHub repository settings:

| Secret | Required | Example | Purpose |
|--------|----------|---------|---------|
| `VALIDATION_PROXY_SMOKE_BASE_URL` | Yes | `https://trade-nexus.lona.agency` | Frontend base URL for proxy route calls |
| `VALIDATION_PROXY_SMOKE_SHARED_KEY` | Yes | `smoke-shared-...` | Shared key accepted only by proxy smoke auth path |
| `VALIDATION_PROXY_SMOKE_PARTNER_KEY` | Yes | `partner-bootstrap` | Partner bootstrap key used to mint runtime bot key each run |
| `VALIDATION_PROXY_SMOKE_PARTNER_SECRET` | Yes | `<redacted>` | Partner bootstrap secret used to mint runtime bot key each run |
| `VALIDATION_PROXY_SMOKE_OWNER_EMAIL` | Yes | `smoke.validation+proxy@lona.agency` | Registration owner identity for runtime bot bootstrap |
| `VALIDATION_PROXY_SMOKE_BOT_NAME` | No | `validation-proxy-smoke` | Registration bot name for runtime bot bootstrap |
| `VALIDATION_PROXY_SMOKE_API_KEY` | No | `tnx.bot.<botId>.<keyId>.<secret>` | Fallback static runtime key only when bootstrap credentials are unavailable |

Optional environment overrides are supported by the script, but are not required for standard runs.

## Controlled Credential Model

1. Workflow sends `VALIDATION_PROXY_SMOKE_SHARED_KEY` in `X-Validation-Smoke-Key`.
2. Proxy accepts smoke auth only for:
   - `POST /api/validation/bots/registrations/partner-bootstrap`
   - `POST /api/validation/runs`
   - `GET /api/validation/runs/{runId}`
   - `GET /api/validation/runs/{runId}/artifact`
3. Smoke script first bootstraps a runtime bot key through the web proxy partner-bootstrap route and reads `issuedKey.rawKey` in-memory only.
4. Script calls the three target routes using that runtime bot key via `X-API-Key`.
5. Script never writes shared key, partner secret, or full runtime bot key into artifacts.

## Rotation & Ownership

- **Rotation owner**: CloudOps
- **Rotation trigger**: on compromise, role handoff, or scheduled key hygiene.

Rotation procedure:

1. Generate a new smoke shared key.
2. Update frontend server env `VALIDATION_PROXY_SMOKE_SHARED_KEY` (Vercel project `trade-nexus`) and redeploy.
3. Update GitHub Actions secret `VALIDATION_PROXY_SMOKE_SHARED_KEY`.
4. Rotate partner bootstrap credential pair:
   - Backend env (`PLATFORM_BOT_PARTNER_CREDENTIALS_JSON`) in Container App.
   - GitHub Actions secrets `VALIDATION_PROXY_SMOKE_PARTNER_KEY` + `VALIDATION_PROXY_SMOKE_PARTNER_SECRET`.
5. Trigger `validation-proxy-smoke` workflow manually.
6. Verify artifact result is `PASS` and all three target routes are non-401.

## Logging / Secret Hygiene

- Do not run with shell tracing (`set -x`) in CI steps handling secrets.
- Do not paste auth headers, tokens, or full secret values into issues/PR comments.
- Evidence comments should include only:
  - workflow run URL,
  - artifact name/link,
  - `runId`,
  - route `requestId` values.

## Evidence Extraction

From uploaded artifacts:

- `*.txt`: concise pass/fail summary and request IDs.
- `*.tsv`: route-level status table for quick scanning.
- `*.json`: machine-readable full result for automation and audits.

## Issue Hygiene Templates

### OPEN Status Comment (#333)

```text
Status: OPEN (issue #333)
- Workflow run: <actions-run-url>
- Artifact: <artifact-name-or-run-url>
- Result: <PASS/FAIL>
- runId: <runId>
- requestIds: <create-run>, <get-run>, <get-artifact>
```

### MERGED Evidence Comment (#333)

```text
Status: MERGED
- PR: <pr-url> (closes #333)
- Workflow run: <actions-run-url>
- Artifact: <artifact-name-or-run-url>
- runId: <runId>
- requestIds: <create-run>, <get-run>, <get-artifact>
```
