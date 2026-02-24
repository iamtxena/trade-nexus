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
| `VALIDATION_PROXY_SMOKE_CLERK_SECRET_KEY` | Yes | `sk_live_...` | Clerk Backend API key used to mint a short-lived session token |
| `VALIDATION_PROXY_SMOKE_CLERK_USER_ID` | Yes | `user_...` | Dedicated smoke account identity |

Optional environment overrides are supported by the script, but are not required for standard runs.

## Controlled Credential Model

1. Workflow uses `VALIDATION_PROXY_SMOKE_CLERK_SECRET_KEY` + dedicated smoke `user_id` (controlled identity).
2. Script creates a short-lived Clerk session and session JWT non-interactively.
3. Script calls proxy routes with bearer + `__session` cookie auth.
4. Script revokes the temporary Clerk session after execution.
5. Script never writes token material into artifacts.

## Rotation & Ownership

- **Rotation owner**: CloudOps
- **Rotation trigger**: on compromise, role handoff, or scheduled key hygiene.

Rotation procedure:

1. Rotate Clerk backend secret key in Clerk Dashboard.
2. Update GitHub secret `VALIDATION_PROXY_SMOKE_CLERK_SECRET_KEY`.
3. If smoke user changes, update `VALIDATION_PROXY_SMOKE_CLERK_USER_ID`.
4. Trigger `validation-proxy-smoke` workflow manually.
5. Verify artifact result is `PASS` and all three routes are non-401.

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
