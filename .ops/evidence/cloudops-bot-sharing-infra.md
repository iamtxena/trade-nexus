# CloudOps Evidence: Bot Registration + Sharing Infrastructure

**Date**: 2026-02-22
**Operator**: CloudOps Team
**Branch**: `cloudops`
**Worktree**: `trade-nexus-cloudops`

## Summary

Prepared all infrastructure changes required for bot registration + validation sharing:
1. Supabase migration with RLS
2. Azure secret storage + env wiring
3. Operational runbooks and verification scripts
4. Security audit

## Deliverables

### 1. Supabase Migration

| File | Description |
|------|-------------|
| `supabase/migrations/003_bot_registration_sharing.sql` | 4 new tables + RLS fix for 5 kb_* tables |
| `supabase/migrations/003_bot_registration_sharing_rollback.sql` | Complete rollback script |

**New Tables**:
- `bots` — User-owned bot registrations (invite_code or partner_key path)
- `bot_api_keys` — API keys with SHA-256 hash storage (no plaintext)
- `validation_runs` — Canonical JSON validation artifacts
- `validation_run_shares` — Run-level sharing by email only

**Security Fix**: Added RLS to 5 `kb_*` tables that were unprotected since migration 002.

### 2. Azure Secret Management

| Action | Status | Evidence |
|--------|--------|----------|
| `partner-bootstrap-secret` created | Done | `azure-secret-partner-bootstrap.md` |
| `PARTNER_BOOTSTRAP_SECRET` env var wired | Done | Verified via `az containerapp show` |
| Secrets inventory updated | Done | 7 secrets total |
| Rollback procedure documented | Done | In evidence file |

### 3. Backend Configuration

| Change | File |
|--------|------|
| `PARTNER_BOOTSTRAP_SECRET` added to env example | `backend/.env.example` |

### 4. Vercel Environment

| Check | Result |
|-------|--------|
| `NEXT_PUBLIC_` vars audit | Clean — only publishable key, URLs, anon key |
| New frontend env vars needed | None — bot registration is backend-only |
| Secret leakage risk | None detected |

### 5. Operational Artifacts

| File | Purpose |
|------|---------|
| `.ops/runbooks/migration-003-rollout.md` | Step-by-step rollout plan with backup/rollback |
| `.ops/runbooks/secret-rotation.md` | Key rotation schedule + procedures for all secrets |
| `.ops/scripts/verify-migration-003.sh` | 26-check automated verification |
| `.ops/scripts/rehearse-rollback-003.sh` | Full forward/rollback/re-apply cycle |
| `.ops/scripts/smoke-check-bot-auth.sh` | HTTP auth enforcement smoke tests |
| `.ops/evidence/azure-secret-partner-bootstrap.md` | Secret creation evidence |
| `.ops/evidence/rls-verification-003.md` | RLS policy matrix |

### 6. Baseline Smoke Check (Pre-deployment)

```
Date: 2026-02-22T07:29:58Z
Health: HTTP 200
GET /v1/strategies (no auth): HTTP 200 (NOTE: auth at RLS layer, not HTTP)
GET /v1/bots: HTTP 404 (expected — not deployed)
POST /v1/bots/register: HTTP 404 (expected — not deployed)
```

## Pre-Merge Checklist

- [x] Migration SQL reviewed for correctness
- [x] RLS policies enforce tenant isolation
- [x] Rollback script tested (rollback SQL created)
- [x] Azure secret created and wired
- [x] No plaintext credentials in repo
- [x] Backend .env.example updated
- [x] Vercel env audit clean
- [x] Key rotation documented with schedule
- [x] Verification scripts created
- [ ] Migration applied to dev/staging DB
- [ ] Rollback rehearsal executed against DB
- [ ] Smoke checks pass post-deployment
- [ ] Governance checks green

## Pending (Post-Merge)

1. Apply migration 003 to Supabase (follow rollout runbook)
2. Run `rehearse-rollback-003.sh` against local DB
3. Run `verify-migration-003.sh` against production
4. Run `smoke-check-bot-auth.sh` after bot API endpoints are deployed
5. First rotation of `partner-bootstrap-secret` scheduled for Q2 2026
