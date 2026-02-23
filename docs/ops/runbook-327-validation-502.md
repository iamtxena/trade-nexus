# Runbook: Validation Web 502 — ML Backend Target Wiring

| Field       | Value                          |
| ----------- | ------------------------------ |
| Issue       | #327 (parent #325)             |
| Severity    | P0                             |
| Service     | `trade-nexus` frontend (Vercel)|
| Affected    | `/api/validation/*` routes     |
| Date opened | 2026-02-23                     |

## Root Cause

The Next.js validation proxy at
`frontend/src/lib/validation/server/platform-api.ts` resolves its backend
target from the `ML_BACKEND_URL` environment variable:

```ts
const DEFAULT_PLATFORM_BASE_URL =
  process.env.ML_BACKEND_URL ?? 'http://localhost:8000';
```

When `ML_BACKEND_URL` is **not set** in Vercel (Production or Preview), the
proxy falls back to `http://localhost:8000`. Because there is no local server
inside the Vercel function runtime, every request to `/api/validation/*`
returns **502 Bad Gateway**.

## Fix

### 1. Set the Vercel environment variable

In the Vercel project dashboard:

| Variable          | Value                            | Environments         |
| ----------------- | -------------------------------- | -------------------- |
| `ML_BACKEND_URL`  | `https://api-nexus.lona.agency`  | Production, Preview  |

After saving, **redeploy** (Vercel > Deployments > Redeploy) to pick up the
new value.

### 2. Code hardening (this PR)

- **Server proxy** (`platform-api.ts`): throws at startup if
  `ML_BACKEND_URL` is unset or points to a local address in production.
- **CLI client** (`cli/lib/platform-api.ts`): logs a warning when the env var
  is missing.
- **`.env.example`**: documents the requirement clearly.

## Verification

1. **Vercel logs** — confirm the deployment starts without the
   `ML_BACKEND_URL is not set` error.
2. **Smoke test** — `curl -s -o /dev/null -w '%{http_code}'
   https://trade-nexus.lona.agency/api/validation/health` should return `200`
   (or the expected status from the ML backend).
3. **Preview deployment** — open a PR preview URL and hit any
   `/api/validation/*` endpoint; it should proxy to
   `https://api-nexus.lona.agency`.

## Rollback

If the hardening causes issues:

1. Set `ML_BACKEND_URL=https://api-nexus.lona.agency` in Vercel and redeploy
   (this alone fixes the 502 regardless of the code change).
2. Revert the code change if needed — the only behavioural difference is the
   localhost fallback returns; requests still succeed once the env var is set.

## Prevention

- The startup-time check prevents silent fallback to localhost in production.
- Future CI can add a `vercel env pull` step to validate required env vars
  before deploy.
