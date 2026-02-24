# Secret Rotation Policy & Procedures

**Owner**: CloudOps Team
**Created**: 2026-02-21
**Review Cadence**: Quarterly

## Secret Inventory

| Secret | Location | Rotation Period | Owner | Notes |
|--------|----------|----------------|-------|-------|
| `partner-bootstrap-secret` | Azure Container App | 90 days | CloudOps | Bot partner registration path |
| `xai-api-key` | Azure + Vercel | On compromise | Dev Team | AI provider key |
| `langsmith-api-key` | Azure + Vercel | 180 days | Dev Team | Observability |
| `lona-agent-token` | Azure + Vercel | 30 days (TTL) | Auto-renew | Gateway token, auto-renews |
| `supabase-key` | Azure + Vercel | On compromise | CloudOps | Service role key |
| `live-engine-service-api-key` | Azure + Vercel | 90 days | CloudOps | Execution bridge |
| `VALIDATION_PROXY_SMOKE_BASE_URL` | GitHub Actions | On endpoint change | CloudOps | Validation proxy smoke target URL |
| `VALIDATION_PROXY_SMOKE_SHARED_KEY` | GitHub Actions + Vercel | On compromise | CloudOps | Proxy smoke shared auth key |
| `VALIDATION_PROXY_SMOKE_API_KEY` | GitHub Actions | On compromise | CloudOps | Runtime bot key forwarded by smoke |
| `CLERK_SECRET_KEY` | Vercel only | On compromise | Dev Team | Auth provider |
| `UPSTASH_REDIS_REST_TOKEN` | Vercel only | On compromise | Dev Team | Cache |
| `SUPABASE_SERVICE_ROLE_KEY` | Vercel only | On compromise | CloudOps | DB admin access |

## Rotation Schedule

| Quarter | Actions |
|---------|---------|
| Q1 (Jan-Mar) | Rotate `partner-bootstrap-secret`, `live-engine-service-api-key` |
| Q2 (Apr-Jun) | Rotate `langsmith-api-key`, audit all secrets |
| Q3 (Jul-Sep) | Rotate `partner-bootstrap-secret`, `live-engine-service-api-key` |
| Q4 (Oct-Dec) | Rotate `langsmith-api-key`, annual full audit |

## Rotation Procedures

### partner-bootstrap-secret (Azure)

```bash
# 1. Generate new secret
NEW_SECRET=$(openssl rand -base64 32 | tr -d '/+=' | head -c 48)

# 2. Update Azure secret
az containerapp secret set \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  --secrets partner-bootstrap-secret="$NEW_SECRET"

# 3. Restart container app to pick up new secret
az containerapp revision restart \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  --revision <active-revision>

# 4. Verify health
curl -s https://trade-nexus-backend.whitecliff-198cd26a.westeurope.azurecontainerapps.io/health

# 5. Notify partners of new key (via secure channel, NOT email/Slack)
```

**Rollback**: Set the previous secret value using the same `az containerapp secret set` command.

### live-engine-service-api-key (Azure + Vercel)

```bash
# 1. Generate new key
NEW_KEY=$(openssl rand -hex 32)

# 2. Update in Azure
az containerapp secret set \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  --secrets live-engine-service-api-key="$NEW_KEY"

# 3. Update in Vercel (frontend)
vercel env rm LIVE_ENGINE_SERVICE_KEY production
echo "$NEW_KEY" | vercel env add LIVE_ENGINE_SERVICE_KEY production

# 4. Update in live-engine Vercel project
# (coordinate with live-engine team)

# 5. Redeploy both services
# 6. Verify bridge connectivity
```

### Supabase Keys (Emergency only)

Supabase keys are rotated via the Supabase Dashboard:
1. Go to Project Settings → API
2. Generate new keys
3. Update ALL services that reference the key (Azure + Vercel)
4. Verify connectivity from all services

**WARNING**: Rotating Supabase keys affects BOTH trade-nexus AND live-engine (shared DB).

## Emergency Rotation (Compromise Response)

If a secret is suspected compromised:

1. **Immediately rotate** the affected secret using procedures above
2. **Revoke** any active sessions/tokens using the old secret
3. **Audit** access logs for unauthorized usage
4. **Notify** team lead and security contact
5. **Document** incident in `.ops/evidence/incident-YYYY-MM-DD.md`

## Vercel Environment Audit

### Frontend env vars (Vercel)

| Variable | Type | Safe to Expose | Notes |
|----------|------|---------------|-------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Public | Yes | Clerk publishable key (designed for client) |
| `NEXT_PUBLIC_CLERK_SIGN_*_URL` | Public | Yes | URL paths only |
| `NEXT_PUBLIC_SUPABASE_URL` | Public | Yes | Project URL (public) |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Public | Yes | Anon key (RLS-protected) |
| `CLERK_SECRET_KEY` | Server | No | Keep server-only |
| `SUPABASE_SERVICE_ROLE_KEY` | Server | No | Bypasses RLS |
| `XAI_API_KEY` | Server | No | AI provider billing |
| `LANGSMITH_API_KEY` | Server | No | Observability |
| `UPSTASH_REDIS_REST_TOKEN` | Server | No | Cache access |
| `LONA_AGENT_REGISTRATION_SECRET` | Server | No | Gateway auth |
| `LONA_AGENT_TOKEN` | Server | No | Gateway auth |
| `LIVE_ENGINE_SERVICE_KEY` | Server | No | Execution bridge |

**Verdict**: No secrets leak through `NEXT_PUBLIC_` variables. All sensitive vars are server-only.

### No new frontend env vars needed

Bot registration is handled entirely by the backend. The frontend's "Shared Validation" UX surface will use existing Clerk auth + API routes to the backend. No new Vercel env vars required for v1.

## Least-Privilege Checklist

- [x] `partner-bootstrap-secret` only accessible to backend container
- [x] No secrets in Git repo, issues, or comments
- [x] ACR credentials stored as Azure Container App secret (not in workflow)
- [x] `NEXT_PUBLIC_` vars contain only safe-to-expose values
- [x] Supabase `anon_key` protected by RLS policies
- [x] Service role key restricted to server-side only
- [ ] ACR admin auth should migrate to managed identity (future improvement)
