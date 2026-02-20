# Trade Nexus — Resource Map

> **Owner**: Team VOps (Cloud DevOps)
> **Last updated**: 2026-02-18
> **Scope**: All cloud resources for the trade-nexus validation program

## Azure Resources

| Resource | Type | Resource Group | Location | FQDN / Endpoint | VOps Owned |
|----------|------|----------------|----------|------------------|------------|
| trade-nexus-backend | Container App | trade-nexus | westeurope | trade-nexus-backend.whitecliff-198cd26a.westeurope.azurecontainerapps.io | Yes |
| trade-nexus-env | Container App Environment | trade-nexus | westeurope | — | Yes |
| tradenexusacr | Container Registry (Basic) | trade-nexus | westeurope | tradenexusacr.azurecr.io | Yes |
| trade-nexus-kv | Key Vault | trade-nexus | westeurope | — | Yes (RBAC gap — see IAM doc) |
| rg-openclaw-trader | Resource Group | — | westeurope | — | Related, not primary |

## Container App Configuration

| Property | Value |
|----------|-------|
| Image | tradenexusacr.azurecr.io/trade-nexus-backend:\<commit-sha\> |
| Min replicas | 0 (scale-to-zero) |
| Max replicas | 10 |
| Active revision | trade-nexus-backend--0000039 (100% traffic) |
| Health check | GET /health (uvicorn, port 8000) |
| Deployment trigger | Push to main with backend/** changes |

## Container App Secrets

| Secret Name | Purpose |
|-------------|---------|
| xai-api-key | xAI Grok API credential |
| supabase-key | Supabase service role key |
| langsmith-api-key | LangSmith observability token |
| lona-agent-token | Lona Gateway auth (30-day TTL) |
| tradenexusacrazurecrio-tradenexusacr | ACR pull credential (managed) |

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

## External Services

| Service | Purpose | Endpoint | VOps Owned |
|---------|---------|----------|------------|
| Supabase | PostgreSQL 15 + RLS | Project dashboard | Yes (provisioning) |
| Vercel (frontend) | Next.js 16 hosting | Auto-deploy from main | Yes (env vars) |
| Vercel (live-engine) | Market data + trading | live.lona.agency | Yes (env vars) |
| Clerk | Authentication | clerk.com dashboard | Yes (keys) |
| Upstash Redis | Distributed cache | REST API | Yes (tokens) |
| LangSmith | AI observability | smith.langchain.com | Yes (API key) |
| Lona Gateway | Strategy/backtest platform | gateway.lona.agency | Yes (agent token) |

## GitHub Actions Secrets

| Secret | Purpose | Rotation |
|--------|---------|----------|
| AZURE_CREDENTIALS | Azure AD service principal | Annual |
| ACR_LOGIN_SERVER | tradenexusacr.azurecr.io | Static |
| ACR_USERNAME | Registry service account | Annual |
| ACR_PASSWORD | Registry access token | Annual |
| NPM_TOKEN | npm publishing (SDK) | Annual |

## CI/CD Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| backend-deploy.yml | Push to main (backend/**) | Build, push ACR, deploy Container App |
| contracts-governance.yml | All `pull_request` events; push to `main` when contract/backend/docs paths change | OpenAPI lint, contract tests, replay preflight, review gates |
| docs-governance.yml | All `pull_request` events; push to `main` when `docs/**`, `docs/portal-site/**`, `scripts/docs/**`, `CONTRIBUTING.md`, or `.github/workflows/docs-governance.yml` changes | Docusaurus build, link validation, frontmatter and stale-ref checks |
| llm-package-governance.yml | All `pull_request` events; push to `main` when docs/scripts paths change | LLM package generation, validation, and committed-artifact drift check |
| publish-sdk.yml | Manual or sdk-v* tag | SDK regeneration and npm publish |

## Operational Scripts

| Script | Purpose | Location |
|--------|---------|----------|
| smoke-check.sh | Post-deploy health validation | .ops/scripts/ |
| ops-drill.sh | 5-scenario operational readiness | .ops/scripts/ |
| rollback.sh | Revision rollback with validation | .ops/scripts/ |
| fix-kv-rbac.sh | Key Vault RBAC remediation | .ops/scripts/ |

## SLO Targets

| SLO | Target | Current |
|-----|--------|---------|
| SLO-1 Availability | 99.0% (7-day) | Monitoring |
| SLO-2 Warm Latency | p95 < 500ms | 133-140ms PASS |
| SLO-3 Cold Start | p95 < 120s | 96s PASS |
| SLO-4 Error Rate | < 5% 5xx/hour | 0% PASS |
| SLO-5 Rollback Time | < 5 min | TBD |
