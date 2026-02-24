# Trade Nexus — IAM & Secrets Ownership

> **Owner**: Team VOps
> **Last updated**: 2026-02-24
> **Governance**: Only VOps provisions, rotates, or modifies secrets and IAM roles.

## Service Principal

| Property | Value |
|----------|-------|
| Display name | `trade-nexus-github` |
| App ID | `7b72321f-4018-4344-80ce-d89c7fd5ad1f` |
| Object ID | `686cfecc-30f6-4302-9c35-7a6d36cb4d11` |
| Auth method | OIDC Federation (GitHub Actions) |
| Credentials | None (no passwords/certificates — OIDC only) |
| Role | Contributor on `trade-nexus` resource group |
| Risk | Over-provisioned — should scope to AcrPush + Container Apps only |

## Managed Identity

| Property | Value |
|----------|-------|
| Type | System-assigned (Container App) |
| Principal ID | `6759fd3c-1516-4d84-ac79-43668cd8f17d` |
| Tenant ID | `478adfc8-a82d-4cc9-b064-32ca91c7db7a` |
| Role | AcrPull on `tradenexusacr` |

## Key Vault

| Property | Value |
|----------|-------|
| Name | `trade-nexus-kv` |
| URI | `https://trade-nexus-kv.vault.azure.net/` |
| Location | West Europe |
| Auth | RBAC (no access policies) |
| Soft delete | 90 days |
| Public access | Enabled |
| Status | Created — secrets not yet migrated from Container App env vars |

## RBAC Gap: Key Vault Access

**Issue**: `trade-nexus-kv` exists but the CLI user lacks `Microsoft.KeyVault/vaults/secrets/readMetadata/action`.

**Remediation**: Run `.ops/scripts/fix-kv-rbac.sh` (prepared, not yet executed).

**Impact**: Cannot list or manage Key Vault secrets from CLI. Container App secrets are managed separately and are unaffected.

## Secrets Inventory

| Secret | Location(s) | Owner | Rotation | Classification |
|--------|-------------|-------|----------|----------------|
| xai-api-key | Container App secret | VOps | 90 days | API credential |
| supabase-key | Container App secret | VOps | On compromise | DB credential |
| langsmith-api-key | Container App secret | VOps | 90 days | Observability |
| lona-agent-token | Container App secret | VOps | 30-day TTL | Service auth |
| live-engine-service-api-key | Container App secret | VOps | On compromise | Service auth |
| ACR pull credential | Container App secret (managed) | VOps | Auto-managed | Registry |
| AZURE_CREDENTIALS | GitHub Actions secret | VOps | N/A (OIDC) | CI/CD SP |
| ACR_LOGIN_SERVER | GitHub Actions secret | VOps | Static | Registry |
| ACR_USERNAME | GitHub Actions secret | VOps | **Remove after MI migration** | Registry (legacy) |
| ACR_PASSWORD | GitHub Actions secret | VOps | **Remove after MI migration** | Registry (legacy) |
| NPM_TOKEN | GitHub Actions secret | VOps | Annual | SDK publishing |
| VALIDATION_PROXY_SMOKE_BASE_URL | GitHub Actions secret | VOps | On endpoint change | Smoke routing target |
| VALIDATION_PROXY_SMOKE_SHARED_KEY | GitHub Actions secret + Vercel server env | VOps | On compromise | Proxy smoke shared credential |
| VALIDATION_PROXY_SMOKE_PARTNER_KEY | GitHub Actions secret | VOps | On partner credential rotation | Partner bootstrap key for smoke runtime-key minting |
| VALIDATION_PROXY_SMOKE_PARTNER_SECRET | GitHub Actions secret | VOps | On partner credential rotation | Partner bootstrap secret for smoke runtime-key minting |
| VALIDATION_PROXY_SMOKE_OWNER_EMAIL | GitHub Actions secret | VOps | On ownership handoff | Partner bootstrap owner identity for smoke |
| VALIDATION_PROXY_SMOKE_BOT_NAME | GitHub Actions secret | VOps | Rarely | Optional smoke bot registration name |
| VALIDATION_PROXY_SMOKE_API_KEY | GitHub Actions secret | VOps | On compromise | Optional fallback runtime bot key |
| CLERK_SECRET_KEY | Vercel env var | VOps | On compromise | Auth |
| NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY | Vercel env var | VOps | Static | Auth (public) |
| SUPABASE_SERVICE_ROLE_KEY | Vercel env var | VOps | On compromise | DB admin |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | Vercel env var | VOps | Static | DB (public) |
| UPSTASH_REDIS_REST_URL | Vercel env var | VOps | Static | Cache |
| UPSTASH_REDIS_REST_TOKEN | Vercel env var | VOps | On compromise | Cache |
| LIVE_ENGINE_SERVICE_KEY | Vercel env var | VOps | On compromise | Service auth |

## IAM Roles

| Principal | Type | Scope | Permissions | Status |
|-----------|------|-------|-------------|--------|
| CLI user (oid: 1252057e-...) | User | trade-nexus RG | Container App manage, ACR push | Active |
| CLI user (oid: 1252057e-...) | User | trade-nexus-kv | Key Vault Secrets User | **MISSING — RBAC GAP** |
| GitHub Actions SP | Service Principal | trade-nexus RG | ACR push, Container App deploy | Active |
| Supabase service role | API key | Supabase project | Full DB (bypasses RLS) | Active |

## Credential Rotation Status

| Secret | Last Rotated | Next Due | Status |
|--------|-------------|----------|--------|
| OIDC federation | N/A | N/A | No rotation needed (federated) |
| ACR admin creds | N/A | **Remove** | Pending MI migration in CI/CD |
| xai-api-key | Unknown | TBD | Document initial rotation |
| supabase-key | Unknown | On compromise | Supabase dashboard |
| langsmith-api-key | Unknown | TBD | Document initial rotation |
| lona-agent-token | Auto (TTL) | 30-day cycle | Self-rotating via TTL |
| live-engine-service-api-key | 2026-02-21 | On compromise | Just provisioned |
| VALIDATION_PROXY_SMOKE_SHARED_KEY | 2026-02-24 | On compromise | CloudOps-owned smoke shared key |
| VALIDATION_PROXY_SMOKE_PARTNER_SECRET | 2026-02-24 | On partner credential rotation | CloudOps-owned smoke partner bootstrap secret |
| VALIDATION_PROXY_SMOKE_API_KEY | 2026-02-24 | On compromise | Optional fallback runtime key |

## Break-Glass Procedures

### Compromised API Key (xai / langsmith / lona / live-engine)
1. Revoke at provider
2. Generate new key
3. `az containerapp secret set --name trade-nexus-backend --resource-group trade-nexus --secrets <name>=<new-value>`
4. Restart active revision
5. Verify `/health` at `https://api-nexus.lona.agency/health`

### Compromised Service Principal
1. `az ad sp credential reset --id 7b72321f-4018-4344-80ce-d89c7fd5ad1f`
2. Update `AZURE_CREDENTIALS` GitHub secret
3. Trigger test deployment
4. Verify CI/CD pipeline

### Compromised Supabase Key
1. Rotate in Supabase Dashboard
2. Update Container App secret + Vercel env
3. Restart services
4. Verify data access

### Emergency Shutdown
1. `az containerapp update --name trade-nexus-backend --resource-group trade-nexus --max-replicas 0`
2. Traffic stops immediately
3. Verify `api-nexus.lona.agency` returns 503

## Governance Rules

1. **VOps-only mutations**: All Azure/Supabase/Vercel provisioning, IAM changes, and secret rotation must be executed by VOps.
2. **Dev team consumption**: Dev lanes receive env contract docs and `.env.example` templates. They never receive raw credentials.
3. **No hardcoded secrets**: All secret references use environment variables or secret refs.
4. **Rotation protocol**: Manual rotation requires VOps ticket in #223, update in all locations (Container App, GitHub, Vercel).
5. **Audit trail**: All secret changes documented in this file and PR history.

## Open Items

| # | Item | Priority | Owner |
|---|------|----------|-------|
| 1 | Scope SP roles (remove broad Contributor) | Medium | Platform Ops |
| 2 | Migrate CI/CD from ACR admin to SP-based login | Medium | Platform Ops |
| 3 | Disable ACR admin user after CI/CD migration | Medium | Platform Ops |
| 4 | Migrate Container App secrets to Key Vault references | Low | Platform Ops |
| 5 | Add RLS to 5 `kb_*` Supabase tables | High | Data Team |
| 6 | Restrict Key Vault public access | Low | Platform Ops |
| 7 | Add CORS policy to Container App (restrict to `trade-nexus.lona.agency`) | Medium | Platform Ops |
| 8 | Fix Key Vault RBAC for CLI user | Medium | Platform Ops |
