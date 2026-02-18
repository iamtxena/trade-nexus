# Trade Nexus — IAM & Secrets Ownership

> **Owner**: Team VOps
> **Last updated**: 2026-02-18
> **Governance**: Only VOps provisions, rotates, or modifies secrets and IAM roles.

## Secrets Inventory

| Secret | Location(s) | Owner | Rotation | Classification |
|--------|-------------|-------|----------|----------------|
| xai-api-key | Container App secret, backend .env | VOps | Manual | API credential |
| supabase-key | Container App secret, backend .env | VOps | Manual | DB credential |
| langsmith-api-key | Container App secret, backend .env | VOps | Manual | Observability |
| lona-agent-token | Container App secret, backend .env | VOps | 30-day TTL | Service auth |
| ACR pull credential | Container App secret (managed) | VOps | Auto-managed | Registry |
| AZURE_CREDENTIALS | GitHub Actions secret | VOps | Annual | CI/CD SP |
| ACR_LOGIN_SERVER | GitHub Actions secret | VOps | Static | Registry |
| ACR_USERNAME | GitHub Actions secret | VOps | Annual | Registry |
| ACR_PASSWORD | GitHub Actions secret | VOps | Annual | Registry |
| NPM_TOKEN | GitHub Actions secret | VOps | Annual | SDK publishing |
| CLERK_SECRET_KEY | Vercel env var | VOps | Manual | Auth |
| NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY | Vercel env var | VOps | Static | Auth (public) |
| SUPABASE_SERVICE_ROLE_KEY | Vercel env var | VOps | Manual | DB admin |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | Vercel env var | VOps | Static | DB (public) |
| UPSTASH_REDIS_REST_URL | Vercel env var | VOps | Static | Cache |
| UPSTASH_REDIS_REST_TOKEN | Vercel env var | VOps | Manual | Cache |

## IAM Roles

| Principal | Type | Scope | Permissions | Status |
|-----------|------|-------|-------------|--------|
| CLI user (oid: 1252057e-...) | User | trade-nexus RG | Container App manage, ACR push | Active |
| CLI user (oid: 1252057e-...) | User | trade-nexus-kv | Key Vault Secrets User | **MISSING — RBAC GAP** |
| GitHub Actions SP | Service Principal | trade-nexus RG | ACR push, Container App deploy | Active |
| Supabase service role | API key | Supabase project | Full DB (bypasses RLS) | Active |

## RBAC Gap: Key Vault Access

**Issue**: `trade-nexus-kv` exists but the CLI user lacks `Microsoft.KeyVault/vaults/secrets/readMetadata/action`.

**Error**: `Caller is not authorized to perform action on resource`

**Remediation**: Run `.ops/scripts/fix-kv-rbac.sh` (prepared, not yet executed).

**Impact**: Cannot list or manage Key Vault secrets from CLI. Container App secrets are managed separately and are unaffected.

## Governance Rules

1. **VOps-only mutations**: All Azure/Supabase/Vercel provisioning, IAM changes, and secret rotation must be executed by VOps.
2. **Dev team consumption**: Dev lanes (V1-V4) receive env contract docs and `.env.example` templates. They never receive raw credentials.
3. **No hardcoded secrets**: All secret references use environment variables or secret refs.
4. **Rotation protocol**: Manual rotation requires VOps ticket in #223, update in all locations (Container App, GitHub, Vercel).
5. **Audit trail**: All secret changes documented in this file and PR history.
