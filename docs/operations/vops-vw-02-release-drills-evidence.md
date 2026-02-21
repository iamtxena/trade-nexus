# VOPS-VW-02: Cloud Ops Release Drills & Rollback Evidence

**Issue**: #287
**Parent**: #288 (Validation Review Web)
**Date**: 2026-02-20
**Status**: Complete

---

## 1. End-to-End Health Drills

### 1.1 Backend Health Endpoint

| Drill | Endpoint | Status | Latency | Timestamp |
|-------|----------|--------|---------|-----------|
| Cold start | `GET /v1/health` | 200 OK | **89.78s** | 2026-02-20T17:16:14Z |
| Warm request | `GET /v1/health` | 200 OK | **0.14s** | 2026-02-20T17:23:42Z |
| Root health | `GET /health` | 200 OK | 90.42s (cold) | 2026-02-20T17:14:33Z |

**Response (warm)**:
```json
{"status":"ok","service":"trade-nexus-platform-api","timestamp":"2026-02-20T17:16:14Z"}
```

**Finding**: Cold start latency is ~90 seconds on Azure Container Apps. This is due to scale-to-zero configuration. For review-web readiness, consider setting `minReplicas: 1` to eliminate cold starts for trader-facing flows.

### 1.2 Authenticated API Endpoint

| Drill | Endpoint | Status | Latency | Request ID |
|-------|----------|--------|---------|------------|
| Strategy list | `GET /v1/strategies` | 200 OK | 93.13s (cold) | `drill-vops-287-1771608590` |

**Response**:
```json
{
  "requestId": "drill-vops-287-1771608590",
  "items": [{"id":"strat-001","name":"BTC Trend Follow","status":"tested",...}],
  "nextCursor": null
}
```

### 1.3 Live Engine

| Drill | Endpoint | Status | Notes |
|-------|----------|--------|-------|
| Health | `GET /api/health` | 404 | No dedicated health route; Next.js returns 404 for unknown paths |

**Finding**: Live Engine (Next.js on Vercel) has no explicit health endpoint. For operational drills, the root page (`/`) serves as a liveness check. Consider adding `GET /api/health` route for monitoring consistency.

---

## 2. CI/CD Pipeline Verification

### 2.1 Contracts Governance Workflow

**Last green run on main**: [Run 22232542344](https://github.com/iamtxena/trade-nexus/actions/runs/22232542344)
- **Date**: 2026-02-20T16:40:25Z
- **Duration**: 59 seconds
- **All 20 steps passed**:

| Step | Result |
|------|--------|
| Lint OpenAPI contract | Pass |
| Run OpenAPI contract baseline tests | Pass |
| Run OpenAPI contract freeze tests | Pass |
| Run OpenAPI v2 baseline tests | Pass |
| Run OpenAPI validation freeze tests | Pass |
| Run validation schema contract tests | Pass |
| Run SDK validation surface contract tests | Pass |
| Enforce replay gate preflight | Pass |
| Run backend contract behavior tests | Pass |
| Validate SLO and alert baseline alignment | Pass |
| Verify SDK generation drift | Pass |
| Validate mock server routes | Pass |
| Run consumer-driven mock contract checks | Pass |
| Detect incompatible contract changes | Pass |

### 2.2 Backend Deploy Workflow

**Last green run on main**: [Run 22230926844](https://github.com/iamtxena/trade-nexus/actions/runs/22230926844)
- **Date**: 2026-02-20T15:53:43Z
- **All 7 steps passed**:

| Step | Result |
|------|--------|
| Checkout code | Pass |
| Login to Azure | Pass |
| Login to ACR | Pass |
| Build and push Docker image | Pass |
| Deploy to Azure Container Apps | Pass |
| Logout from Azure | Pass |

### 2.3 Local Contract Tests

**Run**: 2026-02-20 (wt-vops-287 worktree)
- **194 tests passed**, 0 failed, 1 warning (Pydantic deprecation)
- **Duration**: 1.88 seconds

### 2.4 SLO/Alert Baseline Check

**Run**: 2026-02-20 (local)
- **Result**: Pass
- **Output**: `SLO/alert baseline validation passed: 5 SLOs, 5 alerts, baseline gate5-slo-alert-baseline.v1`

---

## 3. Rollback Procedure & Evidence

### 3.1 Backend Rollback (Azure Container Apps)

**Method**: Redeploy previous Docker image by SHA tag.

**Steps**:
```bash
# 1. Identify current and previous image tags
az containerapp show \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  --query "properties.template.containers[0].image"

# 2. List available tags in ACR
az acr repository show-tags \
  --name tradenexusacr \
  --repository trade-nexus-backend \
  --orderby time_desc \
  --top 5

# 3. Rollback to previous tag
az containerapp update \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  --image tradenexusacr.azurecr.io/trade-nexus-backend:<previous-sha>

# 4. Verify health
curl https://trade-nexus-backend.whitecliff-198cd26a.westeurope.azurecontainerapps.io/v1/health
```

**Alternative**: Use GitHub Actions `workflow_dispatch` to trigger deploy of a specific commit:
1. Revert commit on `main` (or checkout previous SHA)
2. Trigger `Backend Deploy` workflow manually
3. Verify health endpoint

**Recovery time estimate**: 3-5 minutes (image pull + container start + cold start)

### 3.2 Frontend Rollback (Vercel)

**Method**: Vercel instant rollback via dashboard.

**Steps**:
1. Go to Vercel dashboard → trade-nexus project → Deployments
2. Find previous successful deployment
3. Click "..." → "Promote to Production"
4. Verify site loads

**Recovery time estimate**: < 30 seconds (Vercel instant promotion)

### 3.3 Database Rollback (Supabase)

**Method**: Run inverse migration SQL.

**Steps**:
1. Connect to Supabase SQL editor
2. Run rollback SQL (DROP TABLE statements for new tables)
3. Remove migration file from repo
4. Verify via Supabase table browser

**Note**: Review-web tables are additive (no ALTER on existing tables), so rollback is zero-risk to existing functionality.

See `docs/operations/vops-vw-01-env-secrets-readiness.md` (PR #293) section 3.4 for detailed rollback SQL.

---

## 4. SLO/Alert Baseline Verification

### 4.1 Current SLO Baseline (gate5-slo-alert-baseline.v1)

| SLO ID | Service | SLI | Target | Window |
|--------|---------|-----|--------|--------|
| `platform_api_request_success_rate` | platform-api | 2xx/contractual 4xx rate | ≥99.5% | 30d |
| `risk_pretrade_latency_p95_ms` | risk-pretrade | p95 latency | ≤200ms | 7d |
| `research_market_scan_latency_p95_ms` | research | p95 latency | ≤2500ms | 7d |
| `reconciliation_cycle_success_rate` | reconciliation | success rate | ≥99.0% | 30d |
| `conversation_turn_latency_p95_ms` | conversation | p95 latency | ≤1200ms | 7d |

### 4.2 Current Alert Baseline

| Alert ID | SLO | Condition | Severity |
|----------|-----|-----------|----------|
| `alert_platform_api_success_rate_burn` | success rate | error budget burn 2h ≥5% | SEV-2 |
| `alert_risk_pretrade_latency` | risk latency | p95 >200ms for 15m | SEV-2 |
| `alert_research_latency` | research latency | p95 >2500ms for 15m | SEV-3 |
| `alert_reconciliation_success_rate` | reconciliation | rate <99.0% for 15m | SEV-2 |
| `alert_conversation_turn_latency` | conversation latency | p95 >1200ms for 15m | SEV-3 |

### 4.3 Review-Web SLO Gap Analysis

| Concern | Status | Action Needed |
|---------|--------|---------------|
| Review endpoint success rate | Covered by `platform_api_request_success_rate` | No — review endpoints are part of Platform API |
| Review endpoint latency | Not explicitly covered | Consider adding SLO for review endpoints when #275 contracts land |
| Render pipeline latency | Not covered | Add SLO if HTML/PDF render pipeline is implemented |

---

## 5. Regression Gate Failure Drill

### 5.1 What Happens When Contracts CI Fails

The `contracts-governance` workflow is a required check on PRs that modify:
- `backend/src/platform_api/`
- `backend/tests/contracts/`
- `docs/architecture/`
- `contracts/`

**Failure scenario**: If a PR introduces a breaking contract change:
1. `test_openapi_contract_freeze.py` detects the diff → CI fails
2. `review-governance` job blocks merge (requires Greptile + Cursor review)
3. PR cannot merge to `main` until contract tests pass

**Evidence**: Run 22232351368 (2026-02-20T16:34:47Z) shows a CI failure that was subsequently fixed in run 22232482307 (success).

### 5.2 What Happens When Backend Deploy Fails

If the deploy workflow fails:
1. Azure Container Apps continues running the previous image
2. No downtime — failed deploy is a no-op
3. `docker push` failure → old `:latest` tag stays
4. `container-apps-deploy-action` failure → previous revision stays active

**Recovery**: Fix the issue, push to `main`, workflow re-triggers.

---

## 6. Drill Summary

| Drill | Result | Evidence |
|-------|--------|----------|
| Backend health (cold) | Pass (90s cold start) | `200 OK` at `/v1/health` |
| Backend health (warm) | Pass (0.14s) | `200 OK` at `/v1/health` |
| Authenticated endpoint | Pass | `200 OK` at `/v1/strategies`, requestId: `drill-vops-287-1771608590` |
| Contracts CI (main) | All 20 steps green | [Run 22232542344](https://github.com/iamtxena/trade-nexus/actions/runs/22232542344) |
| Backend deploy CI (main) | All 7 steps green | [Run 22230926844](https://github.com/iamtxena/trade-nexus/actions/runs/22230926844) |
| Local contract tests | 194/194 pass | 1.88s, 0 failures |
| SLO baseline check | Pass | 5 SLOs, 5 alerts verified |
| Rollback procedure | Documented | Azure image tag, Vercel instant, Supabase DROP |

---

## 7. Recommendations

1. **Cold start mitigation**: Set `minReplicas: 1` on Azure Container Apps for the review-web release to avoid 90s cold starts during trader review flows.
2. **Live Engine health route**: Add `GET /api/health` to live-engine for monitoring parity.
3. **Review endpoint SLO**: Add explicit SLO for review-web endpoints when #275 contracts are frozen.
4. **Credentials rotation**: `.azure-secrets.md` remediation completed — credentials rotated, file relocated, deploy verified green (see VOPS-VW-01 §2.1).
