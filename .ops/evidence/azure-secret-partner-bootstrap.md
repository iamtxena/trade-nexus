# Evidence: Azure Secret — partner-bootstrap-secret

**Date**: 2026-02-21
**Operator**: CloudOps Team
**Change**: Added `partner-bootstrap-secret` to Azure Container App

## Actions Taken

### 1. Secret Created
```
az containerapp secret set \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  --secrets partner-bootstrap-secret="<REDACTED>"
```
**Result**: Secret added successfully. Warning issued that container app needs restart for changes to take effect.

### 2. Environment Variable Wired
```
az containerapp update \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  --set-env-vars "PARTNER_BOOTSTRAP_SECRET=secretref:partner-bootstrap-secret"
```
**Result**: Container app updated. New revision created with env var binding.

### 3. Verification
```
az containerapp show --query "properties.template.containers[0].env[?name=='PARTNER_BOOTSTRAP_SECRET']"
```
**Result**:
| Name | SecretRef |
|------|-----------|
| PARTNER_BOOTSTRAP_SECRET | partner-bootstrap-secret |

### 4. Full Secrets Inventory (post-change)
| Secret Name | Purpose |
|-------------|---------|
| langsmith-api-key | Observability |
| live-engine-service-api-key | Live Engine bridge |
| lona-agent-token | Lona Gateway auth |
| supabase-key | Database access |
| tradenexusacrazurecrio-tradenexusacr | ACR pull credentials |
| xai-api-key | AI provider |
| **partner-bootstrap-secret** | **Bot partner registration (NEW)** |

## Rollback
```bash
az containerapp update \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  --remove-env-vars "PARTNER_BOOTSTRAP_SECRET"

az containerapp secret remove \
  --name trade-nexus-backend \
  --resource-group trade-nexus \
  --secret-names partner-bootstrap-secret
```

## Key Rotation
See `.ops/runbooks/secret-rotation.md` for rotation schedule and procedure.
