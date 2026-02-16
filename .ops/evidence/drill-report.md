# Ops Drill Report — 2026-02-16

> Operational readiness drill results for Trade Nexus backend.

## Drill Metadata

| Field | Value |
|-------|-------|
| Date | 2026-02-16 11:45 UTC |
| Operator | Claude Code (automated) |
| Environment | Production (Azure Container Apps, West Europe) |
| Active Revision | `trade-nexus-backend--0000027` |
| Script Version | `ops-drill.sh` (branch `ops/176-178-release-drills`) |

## Scenario Results

### Scenario 1: Health Check Validation
- **Type**: Read-only
- **Risk**: None
- **Status**: PASS
- **Duration**: 106 seconds
- **Details**:
  - Container was in scale-to-zero state; 3 retries needed before first response
  - `/health`: 200 OK, latency 151ms (warm)
  - `/v1/health`: 200 OK, latency 132ms (warm)
  - Cold-start detection: false (initial connection failures masked the cold start)

### Scenario 2: Scale-from-Zero Latency
- **Type**: Read-only (revision deactivate/activate)
- **Risk**: Minimal
- **Status**: PASS
- **Duration**: 106 seconds
- **Cold-start time**: 19.5 seconds
- **SLO-3 target**: p95 < 45s
- **Details**:
  - Deactivated revision `trade-nexus-backend--0000027` to force scale-to-zero
  - Waited 10s for scale-down, then reactivated
  - 2 connection failures before first successful response
  - First response: 200 OK, latency 19,518ms (cold start)
  - Warm follow-up: 200 OK, latency 131ms
  - Cold-start latency (19.5s) is well within SLO-3 target (45s)

### Scenario 3: Rollback Drill
- **Type**: Write (traffic shift)
- **Risk**: Low
- **Status**: SKIP
- **Duration**: 2 seconds
- **Details**:
  - Only 1 revision found — container app is in single-revision mode
  - Cannot perform rollback drill without multiple revisions
  - Rollback will be testable after the next deployment creates a second revision

### Scenario 4: Emergency Shutdown
- **Type**: Write (revision deactivate/activate)
- **Risk**: Medium (~30-60s downtime)
- **Status**: PASS
- **Duration**: 110 seconds
- **Downtime**: 109 seconds (within 120s recovery window)
- **Details**:
  - Deactivated revision `trade-nexus-backend--0000027`
  - Waited 15s; app returned 404 (FQDN still routed but no active revision)
  - Reactivated revision; 2 connection failures before recovery
  - Recovery response: 200 OK, latency 16,538ms (cold start)
  - Warm follow-up: 200 OK, latency 138ms
  - Total recovery within 120s budget

### Scenario 5: Secret Rotation Simulation
- **Type**: Read-only (dry run)
- **Risk**: None
- **Status**: PASS
- **Duration**: 3 seconds
- **Secrets verified**:
  - [x] `xai-api-key`
  - [x] `supabase-key`
  - [x] `langsmith-api-key`
  - [x] `lona-agent-token`

## SLO Scorecard

| SLO | Target | Measured | Status |
|-----|--------|----------|--------|
| Availability (SLO-1) | 99.0% | N/A (point-in-time drill) | — |
| Warm Latency (SLO-2) | p95 < 500ms | 131-151ms | PASS |
| Cold-Start (SLO-3) | p95 < 45s | 19.5s | PASS |
| Error Rate (SLO-4) | < 5% 5xx/hr | 0% during drill | PASS |
| Rollback Time (SLO-5) | < 5 min | SKIP (single revision) | — |

## Findings & Remediation

| # | Finding | Severity | Remediation | Status |
|---|---------|----------|-------------|--------|
| 1 | Container app in single-revision mode; rollback drill skipped | Low | Rollback will be testable after next deployment. Consider switching to multi-revision mode if rollback SLO is critical. | Documented |
| 2 | Deactivated revision returns 404 (not 503) from FQDN | Info | Azure routes to FQDN but no active revision → 404. Smoke-check.sh handles this via retry. | Documented |
| 3 | Cold-start ~19.5s is healthy, well within 45s SLO | Info | No action needed. Monitor for regression. | N/A |
| 4 | Emergency shutdown recovery takes ~109s (near 120s budget) | Low | Cold-start latency (16.5s) is fine; overhead is from deactivate/activate Azure API calls + retry intervals. | Acceptable |

## Postmortem

No drills failed. Scenario 3 (rollback) was skipped due to single-revision mode — this is an expected limitation, not a failure. All read-only and write drills passed within SLO targets.
