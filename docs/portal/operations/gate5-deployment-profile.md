---
title: Gate5 Deployment Profile
summary: Single active deployment target profile and release-gate checklist for Gate5 readiness.
owners:
  - Team F
  - Team G
updated: 2026-02-20
---

# Gate5 Deployment Profile

## Objective

Gate5 enforces one active deployment target profile with no contradictory runtime paths.

## Active Path

1. Azure Container Apps in resource group `trade-nexus` (West Europe).
2. Backend runtime in `trade-nexus-backend`.
3. Images sourced from `tradenexusacr`.
4. Deployment automation via `backend-deploy.yml`.

## Explicitly Inactive Paths

1. AKS multi-cluster profile is not active for Gate5 release.
2. Any client-side provider direct path is disallowed.
3. Any mixed dual-active deployment profile is disallowed.

## Release Readiness Checklist

1. Contract governance checks are green.
2. `contracts-governance` includes explicit Gate5 checks:
   - `pytest backend/tests/contracts/test_sdk_validation_contract_shape.py`
   - `python -m src.platform_api.validation.release_gate_check`
3. `contracts-governance` includes full backend contract behavior suite (`backend/tests/contracts` with OpenAPI baseline/freeze + behavior tests).
4. Replay-gate preflight remains enforced at deploy-time in `.github/workflows/backend-deploy.yml`.
5. Docs governance checks are green.
6. Deployment documentation and runbooks reference a single active profile.
7. Parent `#81` status is updated with deployment evidence links.

## Traceability

- Deployment architecture source: `/docs/architecture/DEPLOYMENT.md`
- Gate workflow process: `/docs/portal/operations/gate-workflow.md`
- Reliability/deployment closure evidence: `/docs/portal/operations/gate5-reliability-deployment-closure.md`
- Reliability parent epic: `#81`
