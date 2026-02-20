# VOPS-VW-01: Cloud Ops Environment & Secrets Readiness

**Issue**: #286
**Parent**: #288 (Validation Review Web)
**Date**: 2026-02-20
**Status**: Complete

---

## 1. Environment Variable Matrix

### 1.1 Backend (Azure Container Apps)

| Variable | Required | Source | Current Status | Review-Web Impact |
|----------|----------|--------|----------------|-------------------|
| `XAI_API_KEY` | Yes | Azure secret `xai-api-key` | Configured | No change |
| `LANGSMITH_API_KEY` | Yes | Azure secret `langsmith-api-key` | Configured | No change |
| `LANGSMITH_PROJECT` | Yes | Env var (hardcoded) | `trade-nexus-backend` | No change |
| `LANGSMITH_TRACING` | Yes | Env var | `true` | No change |
| `SUPABASE_URL` | Yes | Azure secret `supabase-url` | Configured | No change |
| `SUPABASE_KEY` | Yes | Azure secret `supabase-key` | Configured | No change — review tables use same DB |
| `LONA_GATEWAY_URL` | Yes | Env var | `https://gateway.lona.agency` | No change |
| `LONA_AGENT_ID` | Yes | Env var | Configured | No change |
| `LONA_AGENT_NAME` | Yes | Env var | Configured | No change |
| `LONA_AGENT_TOKEN` | Yes | Azure secret `lona-agent-token` | Configured | No change |
| `LIVE_ENGINE_URL` | Yes | Env var | `https://live.lona.agency` | No change |
| `LIVE_ENGINE_SERVICE_API_KEY` | Yes | Azure secret | Configured | No change |
| `HOST` | Yes | Env var | `0.0.0.0` | No change |
| `PORT` | Yes | Env var | `8000` | No change |
| `DEBUG` | No | Env var | `true` (dev only) | No change |

**Review-web verdict**: No new backend env vars required. Review-web endpoints are served by the existing Platform API (v2) using the same Supabase and auth infrastructure. The in-memory state store used by conversations will be extended for review sessions with no additional secrets.

### 1.2 Frontend (Vercel)

| Variable | Required | Source | Current Status | Review-Web Impact |
|----------|----------|--------|----------------|-------------------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Yes | Vercel env | Configured | No change |
| `CLERK_SECRET_KEY` | Yes | Vercel env | Configured | No change |
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Vercel env | Configured | No change |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Vercel env | Configured | No change |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Vercel env | Configured | No change |
| `UPSTASH_REDIS_REST_URL` | Yes | Vercel env | Configured | No change |
| `UPSTASH_REDIS_REST_TOKEN` | Yes | Vercel env | Configured | No change |
| `XAI_API_KEY` | Yes | Vercel env | Configured | No change |
| `LANGSMITH_API_KEY` | Yes | Vercel env | Configured | No change |
| `ML_BACKEND_URL` | Yes | Vercel env | Points to Azure backend | No change |
| `LONA_GATEWAY_URL` | Yes | Vercel env | Configured | No change |
| `LIVE_ENGINE_URL` | Yes | Vercel env | `https://live.lona.agency` | No change |
| `LIVE_ENGINE_SERVICE_KEY` | Yes | Vercel env | Configured | No change |

**Review-web verdict**: No new frontend env vars required. Review web UI authenticates via Clerk and calls existing Platform API routes (proxied through Next.js API routes).

### 1.3 GitHub Actions (CI/CD)

| Secret | Purpose | Current Status | Review-Web Impact |
|--------|---------|----------------|-------------------|
| `AZURE_CREDENTIALS` | Azure login (SP JSON) | Configured (2026-02-13) | No change |
| `ACR_LOGIN_SERVER` | Docker registry URL | Configured | No change |
| `ACR_USERNAME` | ACR auth | Configured | No change |
| `ACR_PASSWORD` | ACR auth | Configured | No change |

**Review-web verdict**: No new CI secrets needed. Backend deploys via existing `backend-deploy.yml` workflow.

---

## 2. Security Audit & Findings

### 2.1 CRITICAL: Plaintext Credentials in Repository

**File**: `.azure-secrets.md` (committed to repo)

**Finding**: This file contains plaintext Azure credentials:
- ACR passwords (primary + secondary)
- Service Principal client secret
- Subscription/tenant IDs

**Risk**: HIGH — anyone with repo read access can extract credentials.

**Remediation**:
1. Rotate ACR password immediately after removing file
2. Rotate Service Principal client secret
3. Remove `.azure-secrets.md` from repository history (`git filter-repo`)
4. Add `.azure-secrets.md` to `.gitignore`
5. Update GitHub Actions secrets with new credentials

**Owner**: Cloud Ops (immediate action required)

### 2.2 Secret Rotation Rules

| Secret | Rotation Period | Owner | Method |
|--------|----------------|-------|--------|
| Azure SP Client Secret | 90 days | Cloud Ops | `az ad sp credential reset` → update `AZURE_CREDENTIALS` GH secret |
| ACR Password | 90 days | Cloud Ops | `az acr credential renew` → update `ACR_PASSWORD` GH secret |
| Supabase Service Key | On breach only | Platform team | Supabase dashboard → update Azure + Vercel |
| Clerk Secret Key | On breach only | Platform team | Clerk dashboard → update Vercel |
| XAI API Key | On breach only | Platform team | xAI console → update Azure + Vercel |
| LangSmith API Key | On breach only | Platform team | LangSmith dashboard → update Azure + Vercel |
| LONA Agent Token | 30 days (TTL) | Platform team | Re-register agent → update Azure |
| Live Engine Service Key | On breach only | Platform team | Live Engine config → update Azure + Vercel |
| Upstash Redis Token | On breach only | Platform team | Upstash console → update Vercel |

### 2.3 Secrets Ownership Matrix

| Environment | Secrets Manager | Access Control |
|-------------|-----------------|----------------|
| Azure Container Apps | Azure Key Vault (via `containerapp secret`) | SP role assignment |
| Vercel | Vercel Environment Variables | Team member access |
| GitHub Actions | GitHub Secrets | Repository admin |
| Supabase | Supabase Dashboard | Project owner |

---

## 3. Supabase Schema Readiness

### 3.1 Current Tables (2 migrations)

**Migration 001** (`001_initial_schema.sql`):
- `strategies` — user strategies with RLS
- `agent_runs` — agent execution records with RLS
- `predictions` — price/volatility predictions with RLS

**Migration 002** (`002_kb_schema.sql`):
- `kb_patterns`, `kb_market_regimes`, `kb_lessons_learned`, `kb_macro_events`, `kb_correlations`

### 3.2 Review-Web Tables Needed (Migration 003 — pending #275 contract freeze)

The review-web flow requires new tables for:
- **review_sessions** — tracks review sessions (run ID, strategy ID, status, reviewer)
- **review_comments** — trader comments on strategy/backtest artifacts
- **review_decisions** — approve/reject/revise decisions with rationale
- **review_artifacts** — JSON-first canonical artifacts (backtest reports, strategy snapshots)

These tables MUST follow the existing patterns:
- UUID primary keys with `gen_random_uuid()`
- `user_id TEXT NOT NULL` column for RLS
- RLS enabled with `auth.jwt() ->> 'sub' = user_id` policy
- `created_at TIMESTAMPTZ DEFAULT now()` timestamps
- `schema_version TEXT NOT NULL DEFAULT '1.0'` for evolution

### 3.3 Migration Promotion Path

```
Local dev → Supabase CLI (supabase db push) → Staging → Production
```

**Promotion steps**:
1. Write migration SQL in `supabase/migrations/003_review_web.sql`
2. Test locally with `supabase db push` against local Supabase
3. Run `supabase db push` against staging project (if available)
4. Run `supabase db push` against production project
5. Verify via `supabase db status`

### 3.4 Migration Rollback Procedure

**Rollback steps for 003_review_web.sql**:
```sql
-- Rollback migration 003
DROP TABLE IF EXISTS review_artifacts CASCADE;
DROP TABLE IF EXISTS review_decisions CASCADE;
DROP TABLE IF EXISTS review_comments CASCADE;
DROP TABLE IF EXISTS review_sessions CASCADE;
```

**Execution**:
1. Connect to Supabase SQL editor (dashboard)
2. Run rollback SQL
3. Remove migration file from `supabase/migrations/`
4. Verify via `supabase db status`

**Note**: Rollback is safe because review-web tables are additive (no existing table modifications). Foreign keys reference only `user_id` (text), not other tables.

---

## 4. Storage & Access Controls for Render Artifacts

### 4.1 JSON Artifacts (Canonical)

- Stored in Supabase `review_artifacts` table as JSONB
- Access controlled by RLS (`user_id` matches JWT `sub`)
- No additional storage infrastructure required

### 4.2 Optional HTML/PDF Renders

- **Current plan**: Derived on-demand from JSON artifacts (no persistent storage)
- **If persistent storage needed**: Use Supabase Storage with RLS bucket policies
- **Access**: Signed URLs with TTL, generated by authenticated API routes

---

## 5. Verification Evidence

| Check | Result | Timestamp |
|-------|--------|-----------|
| Backend health (`/v1/health`) | 200 OK | 2026-02-20T17:16:14Z |
| Contract tests (194/194) | All pass | 2026-02-20T17:18:XX |
| SLO baseline validation | Pass (5 SLOs, 5 alerts) | 2026-02-20T17:17:XX |
| GitHub secrets (4/4) | All configured | 2026-02-13 |
| Backend deploy workflow | Last success: run 22230926844 | 2026-02-20T15:53:43Z |
| Contracts governance workflow | Last success: run 22232542344 | 2026-02-20T16:40:25Z |

---

## 6. Summary & Recommendations

1. **Environment is ready** — No new env vars or secrets needed for review-web.
2. **CRITICAL**: Remove `.azure-secrets.md` from repo and rotate all exposed credentials.
3. **Schema migration** is straightforward (additive tables) — blocked on #275 contract freeze.
4. **Rollback** is zero-risk: drop new tables, no existing schema impact.
5. **Secrets rotation** rules documented above — enforce 90-day rotation for Azure SP and ACR.
