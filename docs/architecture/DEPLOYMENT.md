# Deployment Architecture (Gate5 Active Profile)

## Purpose

Define the single active deployment target profile for Trade Nexus v2 and explicitly mark non-active options.

## Active Profile (Only One)

Trade Nexus v2 deploys to **Azure Container Apps** in the **`trade-nexus`** resource group (West Europe).

### Active Infrastructure

| Component | Active Target | Notes |
| --- | --- | --- |
| Platform backend | `trade-nexus-backend` (Container App) | Public Platform API runtime |
| Container runtime environment | `trade-nexus-env` | Shared Container Apps environment |
| Image registry | `tradenexusacr` | Canonical image source |
| Operational logs | Log Analytics linked to `trade-nexus-env` | Request/risk/orchestrator trace queries |

### Active CI/CD Path

1. Build backend image from `/backend`.
2. Push image to `tradenexusacr`.
3. Deploy image revision to `trade-nexus-backend`.
4. Validate post-deploy health and contract gates.

Authoritative workflow: `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/.github/workflows/backend-deploy.yml`

## Boundary Rules

1. Clients (CLI/Web/OpenClaw/agents) call Platform API only.
2. Provider APIs are called only through platform adapters.
3. No deployment profile may imply client-side provider fallback.
4. Contract-governance checks remain merge gates before release updates.

## Operational Runbook Links

1. Gate workflow: `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/portal/operations/gate-workflow.md`
2. Gate4 incident controls baseline: `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/portal/operations/gate4-incident-runbooks.md`
3. Gate5 deployment profile runbook: `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/portal/operations/gate5-deployment-profile.md`

## Non-Active Profiles (Explicitly Inactive)

The following are not active release paths for Gate5:

1. AKS-based multi-cluster profile (`rg-trading-dev` / `rg-trading-prod`).
2. Mixed target profile with additional active runtime regions.
3. Client-side execution/data provider direct paths.

They remain future architecture options only and require architecture approval before activation.

## Release Gate Requirements

A deployment candidate is release-eligible only when:

1. Contract governance workflow is green.
2. Docs governance workflow is green.
3. LLM package governance workflow is green for docs-affecting PRs.
4. Required Gate5 reliability checks and runbook references are complete.

## Change Control

Any change to active deployment profile must update:

1. `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/DEPLOYMENT.md`
2. `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/portal/operations/gate5-deployment-profile.md`
3. Parent issue status in `#81`

