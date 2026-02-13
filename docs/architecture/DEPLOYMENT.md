# Deployment Architecture

## Overview

Deployment of Trader Brain ecosystem on Azure infrastructure.

## Resource Group Strategy

**IMPORTANT**: We use a **single resource group** for all new Trade Nexus components:

| What | Resource Group | Notes |
|------|---------------|-------|
| **New Trade Nexus components** | `trade-nexus` (West Europe) | Everything we build goes here |
| **Lona Gateway** | Existing Lona RG | Already deployed, don't touch |
| **Live Engine** | Existing Lona RG / Vercel | Already deployed, don't touch |

> **No dev/prod split** for now. We deploy directly to `trade-nexus` resource group.

---

## Trade Nexus Resource Group (West Europe)

**All new services go here**: APIs, Data Module, Agent Platform, etc.

### Available Resources

| Resource | Type | Notes |
|----------|------|-------|
| `trade-nexus-env` | Container App Environment | Shared hosting layer |
| `tradenexusacr` | Container Registry | Push images here |
| `trade-nexus-backend` | Container App | 2 vCPU, 4GB RAM |
| Log Analytics | Auto-created | Shared logs |

### Service Principal
- **Name**: `trade-nexus-github`
- **Role**: Contributor (scoped to resource group)
- **Use**: GitHub Actions deployments

### How to Deploy a New App

```bash
# 1. Push image to ACR
docker build -t tradenexusacr.azurecr.io/my-app:latest .
docker push tradenexusacr.azurecr.io/my-app:latest

# 2. Create Container App
az containerapp create \
  --name my-app \
  --resource-group trade-nexus \
  --environment trade-nexus-env \
  --image tradenexusacr.azurecr.io/my-app:latest \
  --registry-server tradenexusacr.azurecr.io \
  --registry-username tradenexusacr \
  --registry-password <ACR_PASSWORD> \
  --target-port 8000 \
  --ingress external \
  --cpu 0.5 --memory 1.0Gi \
  --min-replicas 0
```

### Cost Model
- Environment + Log Analytics: **~$0 idle** (shared overhead)
- Container App with `--min-replicas 0`: **~$0 when idle**
- Pay only when app has running replicas

---

## Existing Resources (Reference Only)

> **Note**: These exist but we're NOT deploying new Trade Nexus components here.
> New components go to `trade-nexus` RG.

### Trading Platform (North Europe) - Reserved for Lona/Heavy Workloads

| Resource Group | Contains |
|---------------|----------|
| rg-trading-shared | ACR, DNS Zone |
| rg-trading-dev | AKS dev cluster, Redis, Cosmos |
| rg-trading-prod | AKS prod cluster, Redis, Cosmos |

**Use only if** we need AKS for heavy workloads (TimescaleDB, etc.) in the future.

## Simplified Deployment Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              AZURE DEPLOYMENT                                         │
├──────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                       │
│   trade-nexus (West Europe) ← ALL NEW COMPONENTS GO HERE                            │
│   ┌────────────────────────────────────────────────────────────────────────────────┐ │
│   │                                                                                 │ │
│   │   Container Apps Environment: trade-nexus-env                                   │ │
│   │   ACR: tradenexusacr.azurecr.io                                                │ │
│   │                                                                                 │ │
│   │   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐               │ │
│   │   │  Agent Platform │  │  trader-data    │  │  trading-cli    │               │ │
│   │   │  (AI SDK)       │  │  (Data API)     │  │  (CLI Backend)  │               │ │
│   │   │                 │  │                 │  │                 │               │ │
│   │   │  Container App  │  │  Container App  │  │  Container App  │               │ │
│   │   │  min-replicas:0 │  │  min-replicas:0 │  │  min-replicas:0 │               │ │
│   │   └─────────────────┘  └─────────────────┘  └─────────────────┘               │ │
│   │                                                                                 │ │
│   │   ┌─────────────────────────────────────────────────────────────┐             │ │
│   │   │  Azure Blob Storage: tradenexusdata                         │             │ │
│   │   │  • ohlcv/      (Lona-compatible OHLCV data)                 │             │ │
│   │   │  • exports/    (Export files for Lona)                      │             │ │
│   │   └─────────────────────────────────────────────────────────────┘             │ │
│   │                                                                                 │ │
│   └────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                       │
│   External Services (Don't Touch)                                                     │
│   ┌────────────────────────────────────────────────────────────────────────────────┐ │
│   │                                                                                 │ │
│   │   Supabase (Knowledge Base)     Lona Gateway        Live Engine               │ │
│   │   PostgreSQL + pgvector         (Existing RG)       (Vercel/Lona RG)          │ │
│   │                                                                                 │ │
│   └────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                       │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### Component → Resource Mapping

| Component | Resource Group | Type | Notes |
|-----------|---------------|------|-------|
| **Agent Platform API** | `trade-nexus` | Container App | AI SDK orchestrator |
| **trader-data API** | `trade-nexus` | Container App | Scale-to-zero |
| **trading-cli API** | `trade-nexus` | Container App | CLI backend (if needed) |
| **Data Storage (OHLCV)** | `trade-nexus` | Azure Blob Storage | Lona-compatible format |
| **Knowledge Base** | Supabase | PostgreSQL + pgvector | External, managed |
| **Trade Nexus Backend** | `trade-nexus` | Container App | Already deployed ✅ |
| **Lona Gateway** | Lona RG | Container App | **Don't touch** ✅ |
| **Live Engine** | Lona RG / Vercel | - | **Don't touch** ✅ |

### Deployment Decision Tree

```
Is it a lightweight API that can scale to zero?
  └─ YES → trade-nexus Container Apps (West Europe)
  └─ NO (needs persistent storage/high memory)?
       └─ Trading Platform AKS (North Europe)
```

## Data Module Deployment

### Deploy to: `trade-nexus` Container Apps

```bash
# Build and push to trade-nexus ACR
docker build -t tradenexusacr.azurecr.io/trader-data:latest .
docker push tradenexusacr.azurecr.io/trader-data:latest

# Deploy as Container App (scale-to-zero)
az containerapp create \
  --name trader-data \
  --resource-group trade-nexus \
  --environment trade-nexus-env \
  --image tradenexusacr.azurecr.io/trader-data:latest \
  --target-port 8000 \
  --ingress external \
  --cpu 0.5 --memory 1.0Gi \
  --min-replicas 0
```

### Storage: Azure Blob Storage (NOT S3)

```bash
# Create storage account in trade-nexus RG
az storage account create \
  --name tradenexusdata \
  --resource-group trade-nexus \
  --location westeurope \
  --sku Standard_LRS

# Create containers
az storage container create --name ohlcv --account-name tradenexusdata
az storage container create --name exports --account-name tradenexusdata
```

### Data Format: Lona-Compatible OHLCV

**IMPORTANT**: All data must be compatible with Lona's format.

```typescript
// Base OHLCV format (Lona-compatible)
interface OHLCVCandle {
  timestamp: number;    // Unix timestamp (ms)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// Extended format (optional extra columns)
interface ExtendedOHLCV extends OHLCVCandle {
  // Additional columns (Lona will ignore these)
  vwap?: number;
  trades?: number;
  spread?: number;
}
```

**Export for Lona**:
```typescript
// When exporting to Lona, strip to base OHLCV
function exportForLona(data: ExtendedOHLCV[]): OHLCVCandle[] {
  return data.map(({ timestamp, open, high, low, close, volume }) => ({
    timestamp, open, high, low, close, volume
  }));
}
```

**File format**: JSON or CSV
```csv
timestamp,open,high,low,close,volume
1707350400000,42150.5,42300.0,42100.0,42250.0,1234.56
1707354000000,42250.0,42400.0,42200.0,42350.0,1456.78
```

### Repo Structure: `trader-data`

```
trader-data/
├── src/
│   ├── api/              # FastAPI REST
│   ├── cli/              # CLI interface
│   ├── connectors/       # Alpaca, Binance
│   │   ├── alpaca.ts
│   │   └── binance.ts
│   ├── storage/          
│   │   └── azure-blob.ts # Azure Blob adapter
│   └── export/
│       └── lona.ts       # Lona-compatible export
├── Dockerfile
└── README.md
```

## Knowledge Base Deployment

### Option A: Supabase (Recommended for simplicity)

```bash
# Already have Supabase from trade-nexus
# Just add new tables and enable pgvector

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Add tables (see KNOWLEDGE_BASE.md for schema)
```

**Pros**: Easy, managed, already in use
**Cons**: External dependency, potential latency

### Option B: Azure Database for PostgreSQL

```bash
# Create PostgreSQL Flexible Server
az postgres flexible-server create \
  --resource-group rg-trading-shared \
  --name trading-knowledge-db \
  --location northeurope \
  --admin-user kbadmin \
  --sku-name Standard_D2s_v3 \
  --tier GeneralPurpose \
  --storage-size 128 \
  --version 15

# Enable pgvector extension
az postgres flexible-server parameter set \
  --resource-group rg-trading-shared \
  --server-name trading-knowledge-db \
  --name azure.extensions \
  --value vector
```

**Pros**: Same region, lower latency, more control
**Cons**: More to manage

### Recommendation

Start with **Supabase** (existing), migrate to Azure PostgreSQL only if:
- Latency becomes an issue
- Data residency requirements
- Cost optimization needed

## Stock Data Provider

### Start with: Alpaca

**Why Alpaca:**
- Best free tier (unlimited paper trading)
- Real-time data (IEX)
- 5 years historical
- 200 req/min (sufficient)
- Also provides trading API (future live trading)

**Setup:**
```bash
# Environment variables
ALPACA_API_KEY=your_key
ALPACA_API_SECRET=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper trading
# ALPACA_BASE_URL=https://api.alpaca.markets      # Live (later)
```

**Add later:**
- Polygon.io (if need more historical data)
- Finnhub (for additional sentiment data)
- IBKR (for live trading outside US)

## CI/CD Pipeline

### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy Trader Data

on:
  push:
    branches: [main]
    paths:
      - 'trader-data/**'

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Login to ACR
      uses: azure/docker-login@v1
      with:
        login-server: acrtrading.azurecr.io
        username: ${{ secrets.ACR_USERNAME }}
        password: ${{ secrets.ACR_PASSWORD }}
    
    - name: Build and push
      run: |
        docker build -t acrtrading.azurecr.io/trader-data:${{ github.sha }} .
        docker push acrtrading.azurecr.io/trader-data:${{ github.sha }}
    
    - name: Deploy to AKS
      uses: azure/k8s-deploy@v4
      with:
        namespace: trader-data
        manifests: helm/
        images: acrtrading.azurecr.io/trader-data:${{ github.sha }}
```

## DNS / Endpoints

| Service | Endpoint | Environment |
|---------|----------|-------------|
| Data Module API | data.trading.mindsightventures.ai | Prod |
| Data Module API | data-dev.trading.mindsightventures.ai | Dev |
| Knowledge Base | (via Supabase) | - |
| Lona Gateway | gateway.lona.agency | Prod |
| Live Engine | live.lona.agency | Prod |

## Cost Estimates (Azure)

| Resource | Monthly Cost (Est.) | Notes |
|----------|-------------------|-------|
| AKS (Dev) | ~$150 | 2 nodes, B2s |
| AKS (Prod) | ~$300 | 3 nodes, D2s_v3 |
| Azure PostgreSQL | ~$100 | If not using Supabase |
| Blob Storage | ~$20 | 1TB tick data |
| Redis | ~$50 | Basic tier |
| **Total** | ~$520-620/mo | Using Azure credits |

## Next Steps

1. **Create `trader-data` repo** with basic structure
2. **Add Alpaca connector** (stocks + crypto via Alpaca)
3. **Deploy to rg-trading-dev** AKS
4. **Add TimescaleDB** for tick storage
5. **Create CLI** interface
6. **Document API** for agents
