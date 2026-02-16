# Ops Drill Report — 2026-02-16 (v4, Cursor + Greptile review)

> Operational readiness drill results for Trade Nexus backend.
> Re-drilled after addressing 5 automated review findings from Cursor + Greptile.

## Drill Metadata

| Field | Value |
|-------|-------|
| Date | 2026-02-16 14:34 UTC (re-drill v4) |
| Operator | Claude Code (automated) |
| Environment | Production (Azure Container Apps, West Europe) |
| Active Revision | `trade-nexus-backend--0000028` |
| Script Version | `ops-drill.sh` v4 (branch `ops/176-178-release-drills`) |

## Review Fixes Applied (Round 3 — Cursor + Greptile)

| # | Source | Finding | Fix |
|---|--------|---------|-----|
| 1 | Cursor | `CURRENT_REVISION` null when no active revision | Guard against null/empty before deactivation in single-revision path |
| 2 | Greptile | Template SLO-3 stale (45s vs 120s) | Updated `drill-report.md` template to 120s in both scenario 2 and scorecard |
| 3 | Greptile | Deactivation errors silently swallowed (`2>/dev/null`) | Scenarios 2/4 capture stderr, check exit code, abort and restore on failure |
| 4 | Greptile | Post-rollback verification captures jq exit, not az | Split pipeline: az to variable, check exit, then jq separately |

## Review Fixes Applied (Rounds 1 + 2 — Human Reviewer)

| # | Finding | Fix |
|---|---------|-----|
| 1 | False-positive rollback success | `rollback.sh` detects revision mode; fails properly in multi-revision |
| 2 | No fail-safe restore after deactivation | Cleanup trap tracks `DEACTIVATED_REVISIONS[]`, restores on EXIT/INT/TERM |
| 3 | JSON parsing corrupted by stderr | `az_json` helper separates stderr |
| 4 | Drill assumes single active revision | Scenarios 2/4 deactivate/reactivate ALL active revisions |
| 5 | Cold-start under-reports actual startup | Wall-clock elapsed from first attempt to first 200 |
| 6 | SLO-3 mismatch (45s in drill vs 120s in docs) | Drill evaluates against 120s |
| 7 | Emergency shutdown non-blocking | `shutdown_verified` flag required for PASS |
| 8 | Mode detection silent fallback | Fails fast on detection failure |
| 9 | Deactivation failure suppressed in rollback | Captures stderr, fails on error, verifies post-action state |

## Scenario Results

### Scenario 1: Health Check Validation
- **Type**: Read-only
- **Risk**: None
- **Status**: PASS
- **Duration**: 96 seconds
- **Details**:
  - `/health`: 200 OK, first response 23,937ms, warm 135ms
  - `/v1/health`: 200 OK, 133ms
  - Cold-start (wall-clock): 94s

### Scenario 2: Scale-from-Zero Latency
- **Type**: Revision deactivate/activate
- **Risk**: Minimal
- **Status**: PASS
- **Duration**: 114 seconds
- **Cold-start time (wall-clock)**: 96 seconds
- **SLO-3 target**: p95 < 120s (wall-clock)
- **Details**:
  - Deactivated all active revisions with error checking (1: `trade-nexus-backend--0000028`)
  - 96s < 120s SLO-3 target — PASS

### Scenario 3: Rollback Drill
- **Type**: Write (traffic shift)
- **Risk**: Low
- **Status**: SKIP
- **Duration**: 1 second
- **Details**: Single-revision mode, only 1 revision

### Scenario 4: Emergency Shutdown
- **Type**: Revision deactivate/activate (all active revisions)
- **Risk**: Medium (~30-60s downtime)
- **Status**: PASS
- **Duration**: 111 seconds
- **Downtime**: 110 seconds
- **Shutdown verified**: YES (status=404, blocking check)
- **Details**:
  - Deactivation with error checking — succeeded
  - Shutdown confirmed (status=404)
  - Recovery: 200 OK, 19,096ms, warm 137ms

### Scenario 5: Secret Rotation Simulation
- **Type**: Read-only (dry run)
- **Risk**: None
- **Status**: PASS
- **Duration**: 2 seconds
- **Secrets verified**: [x] xai-api-key, [x] supabase-key, [x] langsmith-api-key, [x] lona-agent-token

## SLO Scorecard

| SLO | Target | Measured | Status |
|-----|--------|----------|--------|
| Availability (SLO-1) | 99.0% | N/A (point-in-time) | — |
| Warm Latency (SLO-2) | p95 < 500ms | 133-140ms | PASS |
| Cold-Start (SLO-3) | p95 < 120s (wall-clock) | 96s | PASS |
| Error Rate (SLO-4) | < 5% 5xx/hr | 0% | PASS |
| Rollback Time (SLO-5) | < 5 min | SKIP | — |

## Findings & Remediation

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | Single-revision mode; rollback drill skipped | Low | Documented |
| 2 | Warm latency excellent (133-140ms) | Info | N/A |

## Postmortem

No drills failed. All 13 review findings (9 human + 4 automated) are resolved across 3 review rounds.
