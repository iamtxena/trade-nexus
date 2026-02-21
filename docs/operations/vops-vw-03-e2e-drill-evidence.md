# VOPS-VW-03: End-to-End Validation Review Drill Evidence

**Issue**: #303
**Parent**: #288 (Validation Review Web)
**Unblocks**: #289 (VR-VW-03 Independent CloudOps Review)
**Date**: 2026-02-21
**Status**: Complete

---

## 1. End-to-End Drill Record

Full validation-review lifecycle executed against the live Azure Container Apps backend at
`https://trade-nexus-backend.whitecliff-198cd26a.westeurope.azurecontainerapps.io`.

Authentication: `X-API-Key` header (identity derived via SHA-256 hash per `auth_identity.py`).

### 1.1 Prerequisite Setup

| Step | Endpoint | HTTP | Request ID | Result |
|------|----------|------|------------|--------|
| Create strategy | `POST /v1/strategies` | 201 | `drill-303-strategy-1771664369` | `strat-002` created |
| Create dataset | `POST /v1/datasets/uploads:init` | 202 | `drill-303-dataset-init` | `dataset-002` created |

### 1.2 Validation Run Lifecycle

| Step | Endpoint | HTTP | Request ID | Result |
|------|----------|------|------------|--------|
| 1. Create run | `POST /v2/validation-runs` | 202 | `drill-303-1771664546-create` | Run `valrun-0001` created, status `queued` |
| 2. Retrieve run | `GET /v2/validation-runs/valrun-0001` | 200 | `drill-303-1771664556-get` | Status `completed`, decision `conditional_pass` |
| 3. Retrieve artifact | `GET /v2/validation-runs/valrun-0001/artifact` | 200 | `drill-303-1771664584-artifact` | Full artifact with deterministic checks, agent review, blob refs |

### 1.3 Trader Review Lifecycle

| Step | Endpoint | HTTP | Request ID | Result |
|------|----------|------|------------|--------|
| 5. Add comment | `POST /v2/validation-review/runs/valrun-0001/comments` | 202 | `drill-303-1771664604-comment` | Comment `valcomment-001` persisted |
| 6. Submit decision | `POST /v2/validation-review/runs/valrun-0001/decisions` | 202 | `drill-303-1771664604-decision` | Action `approve`, decision `conditional_pass` |

### 1.4 Optional Render

| Step | Endpoint | HTTP | Request ID | Result |
|------|----------|------|------------|--------|
| 7. Trigger render | `POST /v2/validation-review/runs/valrun-0001/renders` | 202 | `drill-303-1771664604-render` | HTML render `queued` |
| 8. Render status | `GET /v2/validation-review/runs/valrun-0001/renders/html` | 200 | `drill-303-1771664604-render-status` | Status `queued`, artifact pending |

### 1.5 Persisted Final State Verification

| Step | Endpoint | HTTP | Request ID | Result |
|------|----------|------|------------|--------|
| 9. Final state | `GET /v2/validation-review/runs/valrun-0001` | 200 | `drill-303-1771664604-final` | See below |

**Final persisted state** (canonical JSON artifact):
```json
{
  "schemaVersion": "validation-review.v1",
  "run": {
    "id": "valrun-0001",
    "status": "completed",
    "profile": "STANDARD",
    "finalDecision": "conditional_pass"
  },
  "artifact": {
    "deterministicChecks": {
      "indicatorFidelity": { "status": "pass" },
      "tradeCoherence": { "status": "pass" },
      "metricConsistency": { "status": "pass", "driftPct": 0.40 }
    },
    "agentReview": {
      "status": "pass",
      "budget": { "withinBudget": true }
    },
    "traderReview": {
      "required": true,
      "status": "approved"
    }
  },
  "comments": [
    {
      "id": "valcomment-001",
      "body": "Drill-303 trader review: Drawdown within acceptable range. Proceeding to approve.",
      "evidenceRefs": ["blob://validation/drill-303/backtest-report.json"]
    }
  ],
  "decision": {
    "action": "approve",
    "decision": "conditional_pass",
    "reason": "Drill-303: Approved with drawdown monitoring condition.",
    "evidenceRefs": ["blob://validation/drill-303/backtest-report.json"]
  },
  "renders": [
    { "format": "html", "status": "queued" }
  ]
}
```

**Verification**: `traderReview.status` = `approved`, `decision.action` = `approve`, `finalDecision` = `conditional_pass`. Comment, decision, and render all persisted.

---

## 2. Replay-Gate Artifacts

Machine-readable replay-gate reports from merge and deploy CI workflows.

### 2.1 Merge Governance Replay Gate

**Workflow**: `contracts-governance`
**Run**: [22237673993](https://github.com/iamtxena/trade-nexus/actions/runs/22237673993)
**Date**: 2026-02-20T19:15:38Z
**Artifact**: `docs/operations/artifacts/replay-gate-merge-22237673993.json`

```json
{
  "schemaVersion": "validation-replay-gate-report.v1",
  "gateStatus": "pass",
  "gate": {
    "id": "valreplay-001",
    "baselineId": "valbase-001",
    "candidateRunId": "valrun-0002",
    "decision": "pass",
    "mergeBlocked": false,
    "releaseBlocked": false,
    "mergeGateStatus": "pass",
    "releaseGateStatus": "pass",
    "metricDriftDeltaPct": 0.0,
    "metricDriftThresholdPct": 1.0,
    "thresholdBreached": false,
    "summary": "Replay comparison passed without regression."
  }
}
```

### 2.2 Release Deploy Replay Gate

**Workflow**: `backend-deploy`
**Run**: [22237673998](https://github.com/iamtxena/trade-nexus/actions/runs/22237673998)
**Date**: 2026-02-20T19:15:38Z
**Artifact**: `docs/operations/artifacts/replay-gate-deploy-22237673998.json`

```json
{
  "schemaVersion": "validation-replay-gate-report.v1",
  "gateStatus": "pass",
  "gate": {
    "id": "valreplay-001",
    "baselineId": "valbase-001",
    "candidateRunId": "valrun-0002",
    "decision": "pass",
    "mergeBlocked": false,
    "releaseBlocked": false,
    "mergeGateStatus": "pass",
    "releaseGateStatus": "pass",
    "metricDriftDeltaPct": 0.0,
    "metricDriftThresholdPct": 1.0,
    "thresholdBreached": false,
    "summary": "Replay comparison passed without regression."
  }
}
```

### 2.3 CI Steps Evidence

Both workflows now include replay-gate report generation and upload:

| Workflow | Step | Status |
|----------|------|--------|
| contracts-governance | Enforce replay gate preflight for merge-time governance | Pass |
| contracts-governance | Summarize replay gate report (merge governance) | Pass |
| contracts-governance | Upload replay gate report (merge governance) | Pass |
| backend-deploy | Summarize replay gate report (release deploy) | Pass |
| backend-deploy | Upload replay gate report (release deploy) | Pass |

---

## 3. SLO/Alert Baseline Coverage for Review-Web Endpoints

### 3.1 Current Coverage

The SLO baseline (`contracts/config/slo-alert-baseline.v1.json`, version `gate5-slo-alert-baseline.v1`) covers 5 SLOs and 5 alerts.

**Review-web endpoint coverage assessment**:

| SLO | Covers Review-Web? | Rationale |
|-----|--------------------|-----------|
| `platform_api_request_success_rate` (>=99.5%, 30d) | **Yes** | All `/v2/validation-*` and `/v2/validation-review/*` endpoints are part of the Platform API. Success rate SLO covers all API responses. |
| `risk_pretrade_latency_p95_ms` (<=200ms, 7d) | N/A | Risk-specific, not review-web |
| `research_market_scan_latency_p95_ms` (<=2500ms, 7d) | N/A | Research-specific, not review-web |
| `reconciliation_cycle_success_rate` (>=99.0%, 30d) | N/A | Reconciliation-specific |
| `conversation_turn_latency_p95_ms` (<=1200ms, 7d) | N/A | Conversation-specific |

### 3.2 Gap: No Explicit Review-Web Latency SLO

There is no dedicated latency SLO for review-web endpoints. Drill observations:

| Endpoint | Warm Latency |
|----------|-------------|
| `POST /v2/validation-runs` | 0.14s |
| `GET /v2/validation-runs/{runId}` | 0.13s |
| `GET /v2/validation-runs/{runId}/artifact` | 0.18s |
| `POST /v2/validation-review/runs/{runId}/comments` | 0.14s |
| `POST /v2/validation-review/runs/{runId}/decisions` | 0.13s |
| `POST /v2/validation-review/runs/{runId}/renders` | 0.13s |
| `GET /v2/validation-review/runs/{runId}/renders/html` | 0.13s |
| `GET /v2/validation-review/runs/{runId}` | 0.13s |

All endpoints respond within 200ms warm, well within conversational latency targets.

### 3.3 Temporary Waiver

**Waiver**: Explicit review-web latency SLO deferred to post-launch baseline collection.

| Field | Value |
|-------|-------|
| **Scope** | `/v2/validation-*` and `/v2/validation-review/*` latency |
| **Reason** | Insufficient production traffic for meaningful p95 baseline. Success rate is covered by `platform_api_request_success_rate`. |
| **Owner** | Cloud Ops (Team F) |
| **Approved by** | VOPS-VW-03 drill (#303) |
| **Expiry** | 2026-03-21 (30 days post-drill) |
| **Action** | Collect production p95 metrics during first 30 days; add dedicated SLO to `slo-alert-baseline.v2.json` |

---

## 4. Summary

| Deliverable | Status | Evidence |
|-------------|--------|----------|
| E2E drill (create → review → render → decision → verify) | **Complete** | 8 request IDs, run `valrun-0001` |
| Replay-gate artifacts (merge + deploy) | **Complete** | 2 JSON reports, runs 22237673993 / 22237673998 |
| SLO baseline coverage | **Covered** (success rate) + **Waiver** (latency) | Waiver owner: Team F, expiry: 2026-03-21 |
| Docs reconciliation | **Complete** | See companion commits |
