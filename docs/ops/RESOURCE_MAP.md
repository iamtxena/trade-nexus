# Trade Nexus — Resource Map

> **Owner**: Team VOps (Cloud DevOps)
> **Last updated**: 2026-02-24
> **Scope**: All cloud resources for the trade-nexus platform

## Domain Map

| Domain | Service | Host | TLS | Status |
|--------|---------|------|-----|--------|
| `trade-nexus.lona.agency` | Frontend (Next.js) | Vercel | Vercel auto | Live |
| `api-nexus.lona.agency` | Backend API (FastAPI) | Azure Container Apps | Azure managed cert | Live |
| `docs-nexus.lona.agency` | Docs portal | Vercel | Vercel auto | Live |
| `live.lona.agency` | Live Engine (Next.js) | Vercel | Vercel auto | Live |
| `gateway.lona.agency` | Lona Gateway | Azure | Azure | Live |

## DNS Records

| Type | Name | Value | Provider |
|------|------|-------|----------|
| CNAME | `trade-nexus` | `545b87b784bec4d9.vercel-dns-016.com` | Vercel |
| CNAME | `api-nexus` | `trade-nexus-backend.whitecliff-198cd26a.westeurope.azurecontainerapps.io` | Azure |
| TXT | `asuid.api-nexus` | `56B5FC9FD245C8A5B4B3A9E9F26529931113F92541131B2CE8AEEAA5FC2940C1` | Azure (verification) |
| CNAME | `docs-nexus` | `afe58594fb5d5a66.vercel-dns-016.com` | Vercel |
| CNAME | `live` | `833303cf61168e1b.vercel-dns-016.com` | Vercel |
| A | `gateway` | `4.209.43.158` | Azure |

### Certificate

| Domain | Certificate | Binding |
|--------|-------------|---------|
| `api-nexus.lona.agency` | `mc-trade-nexus-en-api-nexus-lona-a-2001` | SNI enabled |

## Azure Resources

| Resource | Type | Resource Group | Location | FQDN / Endpoint | VOps Owned |
|----------|------|----------------|----------|------------------|------------|
| trade-nexus-backend | Container App | trade-nexus | westeurope | api-nexus.lona.agency (custom domain) | Yes |
| trade-nexus-env | Container App Environment | trade-nexus | westeurope | — | Yes |
| tradenexusacr | Container Registry (Basic) | trade-nexus | westeurope | tradenexusacr.azurecr.io | Yes |
| trade-nexus-kv | Key Vault | trade-nexus | westeurope | trade-nexus-kv.vault.azure.net | Yes (RBAC gap — see IAM doc) |
| workspace-tradenexusrzM6 | Log Analytics | trade-nexus | westeurope | — | Yes |

## Container App Configuration

| Property | Value |
|----------|-------|
| Image | tradenexusacr.azurecr.io/trade-nexus-backend:\<commit-sha\> |
| Target port | 8000 |
| External ingress | Yes |
| HTTPS enforced | Yes (`allowInsecure: false`) |
| Min replicas | 0 (scale-to-zero) |
| Max replicas | 10 |
| Resources | 2 CPU, 4Gi RAM, 8Gi ephemeral |
| Cold-start | ~96s measured (2026-02-16) |
| Custom domain | `api-nexus.lona.agency` (SNI, managed cert) |
| Health check | GET /health (uvicorn, port 8000) |
| Deployment trigger | Push to main with backend/** changes |

## Container App Secrets

| Secret Name | Env Var | Purpose |
|-------------|---------|---------|
| xai-api-key | XAI_API_KEY | xAI Grok API credential |
| supabase-key | SUPABASE_KEY | Supabase service role key |
| langsmith-api-key | LANGSMITH_API_KEY | LangSmith observability token |
| lona-agent-token | LONA_AGENT_TOKEN | Lona Gateway auth (30-day TTL) |
| live-engine-service-api-key | LIVE_ENGINE_SERVICE_API_KEY | Live Engine service auth |
| tradenexusacrazurecrio-tradenexusacr | — | ACR pull credential (managed) |

## Container App Environment Variables

| Env Var | Source | Purpose |
|---------|--------|---------|
| XAI_API_KEY | secretRef: xai-api-key | AI model access |
| SUPABASE_URL | plain | Database endpoint |
| SUPABASE_KEY | secretRef: supabase-key | Database auth |
| LANGSMITH_API_KEY | secretRef: langsmith-api-key | Observability |
| LANGSMITH_ENDPOINT | plain | LangSmith API URL |
| LANGSMITH_PROJECT | plain | Project name (trade-nexus-backend) |
| LANGSMITH_TRACING | plain | Enable tracing (true) |
| LONA_GATEWAY_URL | plain | Lona API (gateway.lona.agency) |
| LONA_AGENT_ID | plain | Agent identifier |
| LONA_AGENT_NAME | plain | Agent display name |
| LONA_AGENT_TOKEN | secretRef: lona-agent-token | Lona auth |
| LIVE_ENGINE_URL | plain | Live engine endpoint |
| LIVE_ENGINE_SERVICE_API_KEY | secretRef: live-engine-service-api-key | Live engine auth |

## Vercel Projects

| Project | Domain | Purpose |
|---------|--------|---------|
| trade-nexus (frontend) | `trade-nexus.lona.agency` | Dashboard, API routes, Clerk auth |
| trade-nexus-docs | `docs-nexus.lona.agency` | Documentation portal |
| live-engine | `live.lona.agency` | Market data, paper/live trading |

## External Services

| Service | Purpose | Endpoint | VOps Owned |
|---------|---------|----------|------------|
| Supabase | PostgreSQL 15 + RLS | zonuytrkkvqfyehiviot.supabase.co | Yes (provisioning) |
| Vercel (frontend) | Next.js 16 hosting | trade-nexus.lona.agency | Yes (env vars) |
| Vercel (docs) | Docusaurus hosting | docs-nexus.lona.agency | Yes (env vars) |
| Vercel (live-engine) | Market data + trading | live.lona.agency | Yes (env vars) |
| Clerk | Authentication | clerk.com dashboard | Yes (keys) |
| Upstash Redis | Distributed cache | tops-quetzal-35882.upstash.io | Yes (tokens) |
| LangSmith | AI observability | eu.api.smith.langchain.com | Yes (API key) |
| Lona Gateway | Strategy/backtest platform | gateway.lona.agency | Yes (agent token) |

## GitHub Actions Secrets

| Secret | Purpose | Rotation |
|--------|---------|----------|
| AZURE_CREDENTIALS | Azure AD service principal (OIDC) | N/A (federated) |
| ACR_LOGIN_SERVER | tradenexusacr.azurecr.io | Static |
| ACR_USERNAME | Registry service account | **Remove after MI migration** |
| ACR_PASSWORD | Registry access token | **Remove after MI migration** |
| NPM_TOKEN | npm publishing (SDK) | Annual |
| VALIDATION_PROXY_SMOKE_BASE_URL | Frontend smoke target URL | On endpoint change |
| VALIDATION_PROXY_SMOKE_CLERK_SECRET_KEY | Credentialed smoke auth secret | On compromise |
| VALIDATION_PROXY_SMOKE_CLERK_USER_ID | Credentialed smoke user identity | On account rotation |

## CI/CD Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| backend-deploy.yml | Push to main (backend/**) | Build, push ACR, deploy Container App |
| contracts-governance.yml | All `pull_request` events; push to `main` when contract/backend/docs paths change | OpenAPI lint, contract tests, replay preflight |
| docs-governance.yml | All `pull_request` events; push to `main` when docs paths change | Docusaurus build, link validation |
| llm-package-governance.yml | All `pull_request` events; push to `main` when docs/scripts paths change | LLM package generation and drift check |
| publish-sdk.yml | Manual or sdk-v* tag | SDK regeneration and npm publish |
| validation-proxy-smoke.yml | Manual (`workflow_dispatch`) | Non-interactive credentialed smoke through validation web proxy routes |

## Operational Scripts

| Script | Purpose | Location |
|--------|---------|----------|
| smoke-check.sh | Post-deploy health validation | .ops/scripts/ |
| ops-drill.sh | 5-scenario operational readiness | .ops/scripts/ |
| rollback.sh | Revision rollback with validation | .ops/scripts/ |
| fix-kv-rbac.sh | Key Vault RBAC remediation | .ops/scripts/ |
| validation-proxy-smoke.py | Credentialed validation proxy smoke + artifact generation | .ops/scripts/ |

## Managed Identity

| Identity | Principal ID | Roles |
|----------|-------------|-------|
| System-assigned (Container App) | `6759fd3c-1516-4d84-ac79-43668cd8f17d` | AcrPull on `tradenexusacr` |

## Service Principal

| Name | App ID | Auth | Roles |
|------|--------|------|-------|
| `trade-nexus-github` | `7b72321f-4018-4344-80ce-d89c7fd5ad1f` | OIDC federation (GitHub) | Contributor on `trade-nexus` RG |

## SLO Targets

| SLO | Target | Current |
|-----|--------|---------|
| SLO-1 Availability | 99.0% (7-day) | Monitoring |
| SLO-2 Warm Latency | p95 < 500ms | 133-140ms PASS |
| SLO-3 Cold Start | p95 < 120s | 96s PASS |
| SLO-4 Error Rate | < 5% 5xx/hour | 0% PASS |
| SLO-5 Rollback Time | < 5 min | TBD |
