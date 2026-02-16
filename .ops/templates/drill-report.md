# Ops Drill Report — [DRILL_DATE]

> Operational readiness drill results for Trade Nexus backend.

## Drill Metadata

| Field | Value |
|-------|-------|
| Date | YYYY-MM-DD HH:MM UTC |
| Operator | |
| Environment | Production (Azure Container Apps, West Europe) |
| Active Revision | `trade-nexus-backend--NNNNNNN` |
| Script Version | `ops-drill.sh` (commit `<sha>`) |

## Scenario Results

### Scenario 1: Health Check Validation

- **Type**: Read-only
- **Risk**: None
- **Status**: ☐ PASS / ☐ FAIL / ☐ SKIP
- **Duration**: ___ seconds
- **Details**:
  - `/health`: ___ (status ___, latency ___ms)
  - `/v1/health`: ___ (status ___, latency ___ms)

### Scenario 2: Scale-from-Zero Latency

- **Type**: Read-only
- **Risk**: Minimal
- **Status**: ☐ PASS / ☐ FAIL / ☐ SKIP
- **Duration**: ___ seconds
- **Cold-start time**: ___ seconds
- **SLO-3 target**: p95 < 120s (wall-clock)
- **Details**:

### Scenario 3: Rollback Drill

- **Type**: Write (traffic shift)
- **Risk**: Low
- **Status**: ☐ PASS / ☐ FAIL / ☐ SKIP
- **Duration**: ___ seconds
- **Details**:
  - Rollback to revision: ___
  - Rollback smoke check: ___
  - Restore to revision: ___
  - Restore smoke check: ___

### Scenario 4: Emergency Shutdown

- **Type**: Write (scale to 0)
- **Risk**: Medium (~30-60s downtime)
- **Status**: ☐ PASS / ☐ FAIL / ☐ SKIP
- **Duration**: ___ seconds
- **Downtime**: ___ seconds
- **Details**:
  - Scale-down confirmed: ___
  - 503 verified: ___
  - Recovery time: ___ seconds

### Scenario 5: Secret Rotation Simulation

- **Type**: Read-only (dry run)
- **Risk**: None
- **Status**: ☐ PASS / ☐ FAIL / ☐ SKIP
- **Duration**: ___ seconds
- **Secrets verified**:
  - [ ] `xai-api-key`
  - [ ] `supabase-key`
  - [ ] `langsmith-api-key`
  - [ ] `lona-agent-token`

## SLO Scorecard

| SLO | Target | Measured | Status |
|-----|--------|----------|--------|
| Availability (SLO-1) | 99.0% | — | — |
| Warm Latency (SLO-2) | p95 < 500ms | ___ms | |
| Cold-Start (SLO-3) | p95 < 120s (wall-clock) | ___s | |
| Error Rate (SLO-4) | < 5% 5xx/hr | — | — |
| Rollback Time (SLO-5) | < 5 min | ___s | |

## Findings & Remediation

| # | Finding | Severity | Remediation | Status |
|---|---------|----------|-------------|--------|
| 1 | | | | |

## Postmortem (if any drill failed)

**Root cause**:

**Impact**:

**Action items**:
- [ ]
