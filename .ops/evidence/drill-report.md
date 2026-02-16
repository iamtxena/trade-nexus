# Ops Drill Report — 2026-02-16 (v3, second review round)

> Operational readiness drill results for Trade Nexus backend.
> Re-drilled after addressing 4 follow-up findings from PR #195 second review.

## Drill Metadata

| Field | Value |
|-------|-------|
| Date | 2026-02-16 14:18 UTC (re-drill v3) |
| Operator | Claude Code (automated) |
| Environment | Production (Azure Container Apps, West Europe) |
| Active Revision | `trade-nexus-backend--0000028` |
| Script Version | `ops-drill.sh` v3 (branch `ops/176-178-release-drills`) |

## Review Fixes Applied (Round 2)

| # | Finding | Fix |
|---|---------|-----|
| 1 | SLO-3 mismatch: drill enforced 45s, slo-definitions.md says 120s | `ops-drill.sh` scenario 2 now evaluates against 120s (matching `slo-definitions.md`) |
| 2 | Emergency shutdown verification non-blocking | Scenario 4 now tracks `shutdown_verified` flag; FAIL if app still responds 200 after deactivation |
| 3 | Rollback mode detection silently falls back to "single" | `rollback.sh` now fails fast (exit 1) if `az containerapp show` fails to detect mode |
| 4 | Single-revision deactivation suppresses failure | `rollback.sh` captures deactivation stderr, fails on error; post-action verifies active revision matches target |

## Review Fixes Applied (Round 1)

| # | Finding | Fix |
|---|---------|-----|
| 1 | False-positive rollback success | `rollback.sh` detects revision mode; multi-revision failures properly fail |
| 2 | No fail-safe restore after deactivation | `ops-drill.sh` cleanup trap tracks `DEACTIVATED_REVISIONS[]`, restores on EXIT/INT/TERM |
| 3 | JSON parsing corrupted by stderr | `az_json` helper separates stderr to temp file |
| 4 | Drill assumes single active revision | Scenarios 2/4 deactivate/reactivate ALL active revisions |
| 5 | Cold-start under-reports actual startup | Wall-clock elapsed from first attempt to first 200 |

## Scenario Results

### Scenario 1: Health Check Validation
- **Type**: Read-only
- **Risk**: None
- **Status**: PASS
- **Duration**: 96 seconds
- **Details**:
  - Container was in scale-to-zero state; 2 connection failures before first 200
  - `/health`: 200 OK, first response 24,675ms, warm follow-up 128ms
  - `/v1/health`: 200 OK, latency 128ms
  - Cold-start (wall-clock): 95s

### Scenario 2: Scale-from-Zero Latency
- **Type**: Revision deactivate/activate
- **Risk**: Minimal
- **Status**: PASS
- **Duration**: 114 seconds
- **Cold-start time (wall-clock)**: 96 seconds
- **SLO-3 target**: p95 < 120s (wall-clock) — matches `slo-definitions.md`
- **Details**:
  - Deactivated all active revisions (1: `trade-nexus-backend--0000028`)
  - Waited 10s for scale-down, then reactivated
  - 2 connection failures + 25.4s successful request
  - Wall-clock: 96s < 120s SLO-3 target — **PASS**
  - Script output correctly shows: `SLO-3: p95 < 120s wall-clock`

### Scenario 3: Rollback Drill
- **Type**: Write (traffic shift)
- **Risk**: Low
- **Status**: SKIP
- **Duration**: 2 seconds
- **Details**:
  - Only 1 revision found — single-revision mode
  - Rollback testable after next deployment

### Scenario 4: Emergency Shutdown
- **Type**: Revision deactivate/activate (all active revisions)
- **Risk**: Medium (~30-60s downtime)
- **Status**: PASS
- **Duration**: 112 seconds
- **Downtime**: 111 seconds (within 120s recovery window)
- **Shutdown verified**: YES (status=404 confirmed after deactivation)
- **Details**:
  - Deactivated all active revisions (1: `trade-nexus-backend--0000028`)
  - Waited 15s; **shutdown_verified=true** (status=404, app confirmed down)
  - Reactivated revision; 2 connection failures before recovery
  - Recovery: 200 OK, latency 19,324ms, warm 148ms
  - Wall-clock cold-start: 90s (within 120s budget)

### Scenario 5: Secret Rotation Simulation
- **Type**: Read-only (dry run)
- **Risk**: None
- **Status**: PASS
- **Duration**: 2 seconds
- **Secrets verified**:
  - [x] `xai-api-key`
  - [x] `supabase-key`
  - [x] `langsmith-api-key`
  - [x] `lona-agent-token`

## SLO Scorecard

| SLO | Target | Measured | Status |
|-----|--------|----------|--------|
| Availability (SLO-1) | 99.0% | N/A (point-in-time drill) | — |
| Warm Latency (SLO-2) | p95 < 500ms | 128-148ms | PASS |
| Cold-Start (SLO-3) | p95 < 120s (wall-clock) | 96s | PASS |
| Error Rate (SLO-4) | < 5% 5xx/hr | 0% during drill | PASS |
| Rollback Time (SLO-5) | < 5 min | SKIP (single revision) | — |

## Findings & Remediation

| # | Finding | Severity | Remediation | Status |
|---|---------|----------|-------------|--------|
| 1 | Single-revision mode; rollback drill skipped | Low | Testable after next deployment | Documented |
| 2 | Deactivated revision returns 404 (not 503) | Info | Handled by smoke-check retry | Documented |
| 3 | Warm latency excellent (128-148ms) | Info | Well within 500ms SLO-2 | N/A |

## Postmortem

No drills failed. All script/SLO parity issues from the second review are resolved:
- Scenario 2 now evaluates against 120s (matching `slo-definitions.md`), not 45s
- Scenario 4 requires shutdown verification before PASS — blocking, not advisory
- `rollback.sh` fails fast on mode detection failure and verifies post-action state
- All 9 original + follow-up review findings are addressed
