# Release Evidence — [RELEASE_DATE]

> Per-release validation record for Trade Nexus backend.

## Release Metadata

| Field | Value |
|-------|-------|
| Date | YYYY-MM-DD HH:MM UTC |
| Commit SHA | `<sha>` |
| Image Tag | `tradenexusacr.azurecr.io/trade-nexus-backend:<tag>` |
| Previous Revision | `trade-nexus-backend--NNNNNNN` |
| New Revision | `trade-nexus-backend--NNNNNNN` |
| Deployed By | GitHub Actions (run #NNN) |

## Pre-Release Checks

| Check | Status | Notes |
|-------|--------|-------|
| CI pipeline green | ☐ | |
| No open SEV-1/2 | ☐ | |
| Previous release stable >= 1hr | ☐ | |
| PR approved | ☐ | |
| Breaking changes documented | ☐ N/A | |

## Post-Deploy Validation

| Check | Status | Value |
|-------|--------|-------|
| `GET /health` returns 200 | ☐ | |
| `GET /v1/health` returns 200 | ☐ | |
| Warm latency < 500ms (SLO-2) | ☐ | ___ ms |
| No 5xx errors in first 5 min | ☐ | |
| New revision receiving traffic | ☐ | |

## Rollback Readiness

| Check | Status |
|-------|--------|
| Previous revision still active | ☐ |
| `rollback.sh` tested in last 7 days | ☐ |
| Rollback operator identified | ☐ |

## Sign-Off

| Role | Name | Date |
|------|------|------|
| Deployer | | |
| Reviewer | | |
