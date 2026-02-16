# Release Promotion & Rollback Runbook

> Process for promoting backend releases and rolling back if issues arise.

## Overview

Trade Nexus backend deploys automatically via GitHub Actions when changes merge to `main` under `backend/**`. This runbook covers the validation and rollback procedures surrounding each release.

## Pre-Promotion Checklist

Before merging a backend PR to `main`:

- [ ] All CI checks pass (lint, typecheck, tests, contract governance)
- [ ] No open SEV-1 or SEV-2 incidents
- [ ] Previous release has been stable for >= 1 hour
- [ ] PR has at least one approval
- [ ] Breaking changes documented in PR description

## Promotion Steps

1. **Merge PR to `main`**
   - GitHub Actions triggers `.github/workflows/backend-deploy.yml`
   - Builds Docker image, pushes to `tradenexusacr`, deploys to Container Apps

2. **Monitor CI pipeline**
   - Watch GitHub Actions run: `gh run list --workflow=backend-deploy.yml --limit=1`
   - Expected duration: ~3-5 minutes

3. **Verify new revision**
   ```bash
   az containerapp revision list \
     --name trade-nexus-backend \
     --resource-group trade-nexus \
     -o table
   ```
   - Confirm new revision is active and receiving 100% traffic

4. **Run smoke check**
   ```bash
   .ops/scripts/smoke-check.sh
   ```
   - All endpoints must return 200
   - Warm latency must be < 500ms (SLO-2)

5. **Record evidence**
   - Fill out `.ops/templates/release-evidence.md` for the release
   - Archive in `.ops/evidence/` with date prefix

## Rollback Trigger Criteria

Initiate rollback if ANY of these conditions are met:

| Trigger | Threshold | Detection |
|---------|-----------|-----------|
| Smoke check failure | Fails for > 2 minutes | `smoke-check.sh` returns FAIL |
| Elevated error rate | > 5% 5xx in 5 minutes | Log Analytics / application logs |
| Health endpoint down | > 30 seconds continuous | Synthetic monitoring |
| Critical functionality broken | Any P0 path affected | Manual verification |

## Rollback Procedure

1. **Execute rollback**
   ```bash
   .ops/scripts/rollback.sh
   ```
   - Automatically finds previous revision, shifts traffic, runs smoke check

2. **Verify rollback success**
   - Smoke check passes on previous revision
   - Error rate returns to baseline

3. **Post-rollback actions**
   - Post incident note to the relevant GitHub PR/issue
   - Investigate root cause before re-attempting promotion
   - If the failed revision introduced a database migration, follow the migration rollback procedure separately

## Manual Rollback (if script fails)

```bash
# List revisions
az containerapp revision list \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  -o table

# Activate previous revision (if deactivated)
az containerapp revision activate \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  --revision <previous-revision-name>

# Shift traffic
az containerapp ingress traffic set \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  --revision-weight <previous-revision-name>=100
```

## Future Enhancements

- GitHub environment protection rules in `backend-deploy.yml` (require manual approval for prod)
- Automated canary deployments (10% -> 50% -> 100%)
- Integration with Azure Monitor alerts for automatic rollback triggers
