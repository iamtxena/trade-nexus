# Deployment Architecture

## Overview

Deployment of Trader Brain ecosystem on Azure infrastructure.

## Azure Infrastructure

### Two Resource Ecosystems

| Ecosystem | Resource Group | Region | Purpose |
|-----------|---------------|--------|---------|
| **Trade Nexus** | `trade-nexus` | West Europe | Container Apps (backend services) |
| **Trading Platform** | `rg-trading-*` | North Europe | AKS (Lona, heavy workloads) |

---

## Trade Nexus Resource Group (West Europe)

**Best for**: Lightweight services, APIs, scale-to-zero workloads

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

## Trading Platform (North Europe)

### Resource Groups

| Resource Group | Environment | Region |
|---------------|-------------|--------|
| rg-trading-shared | Shared Infrastructure | North Europe |
| rg-trading-dev | Development | North Europe |
| rg-trading-prod | Production | North Europe |
| rg-trading-lab | Lab/Sandbox | West Europe |

### Available Resources

#### Shared (rg-trading-shared)
- `acrtrading` — Container Registry
- `mindsightventures.ai` — DNS Zone

#### Development (rg-trading-dev)
- `aks-trading-dev` — AKS Cluster
- `trading-dev-redis` — Azure Cache for Redis
- `trading-dev-mongodb` — Cosmos DB (MongoDB API)
- `tradingdevstorage` — Storage Account
- Application Gateway + VNet

#### Production (rg-trading-prod)
- `aks-trading-prod` — AKS Cluster
- `trading-prod-redis` — Azure Cache for Redis
- `trading-prod-mongodb` — Cosmos DB (MongoDB API)
- `tradingprodstorage` — Storage Account
- Application Gateway + VNet

## Component Deployment

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         AZURE TRADING PLATFORM                                       │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   rg-trading-shared (North Europe)                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │  acrtrading.azurecr.io          mindsightventures.ai (DNS)                  │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                           │
│         ┌────────────────────────────────┴────────────────────────────────┐         │
│         │                                                                  │         │
│         ▼                                                                  ▼         │
│   rg-trading-dev (North Europe)                  rg-trading-prod (North Europe)     │
│   ┌───────────────────────────────┐              ┌───────────────────────────────┐  │
│   │                               │              │                               │  │
│   │   AKS: aks-trading-dev        │              │   AKS: aks-trading-prod       │  │
│   │   ┌─────────────────────────┐ │              │   ┌─────────────────────────┐ │  │
│   │   │ Namespaces:             │ │              │   │ Namespaces:             │ │  │
│   │   │ • trader-data           │ │              │   │ • trader-data           │ │  │
│   │   │ • trader-knowledge      │ │              │   │ • trader-knowledge      │ │  │
│   │   │ • trader-cli            │ │              │   │ • trader-cli            │ │  │
│   │   └─────────────────────────┘ │              │   └─────────────────────────┘ │  │
│   │                               │              │                               │  │
│   │   Redis: trading-dev-redis    │              │   Redis: trading-prod-redis   │  │
│   │   Cosmos: trading-dev-mongodb │              │   Cosmos: trading-prod-mongodb│  │
│   │   Storage: tradingdevstorage  │              │   Storage: tradingprodstorage │  │
│   │                               │              │                               │  │
│   └───────────────────────────────┘              └───────────────────────────────┘  │
│                                                                                      │
│   rg-trading-lab (West Europe)                                                      │
│   ┌───────────────────────────────┐                                                 │
│   │  Experimental deployments     │                                                 │
│   │  CI/CD testing                │                                                 │
│   └───────────────────────────────┘                                                 │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Component → Resource Mapping

| Component | Where | Resource | Notes |
|-----------|-------|----------|-------|
| **Trade Nexus Backend** | trade-nexus (WE) | Container App | Already deployed ✅ |
| **trader-data API** | trade-nexus (WE) | Container App | Scale-to-zero, lightweight |
| **trader-cli API** | trade-nexus (WE) | Container App | If needed as service |
| **Knowledge Base** | Supabase | PostgreSQL + pgvector | External, managed |
| **Tick Data (Hot)** | rg-trading-dev (NE) | AKS + TimescaleDB | High memory workloads |
| **Tick Data (Cold)** | trade-nexus (WE) | Storage Account | Parquet files |
| **Lona Gateway** | lona (separate RG) | Container App | Already deployed ✅ |
| **Live Engine** | lona (separate RG) | Vercel | Already deployed ✅ |

### Deployment Decision Tree

```
Is it a lightweight API that can scale to zero?
  └─ YES → trade-nexus Container Apps (West Europe)
  └─ NO (needs persistent storage/high memory)?
       └─ Trading Platform AKS (North Europe)
```

## Data Module Deployment

### New Repo: `trader-data`

```
trader-data/
├── src/
│   ├── api/              # FastAPI REST + WebSocket
│   ├── cli/              # CLI interface
│   ├── connectors/       # Exchange connectors
│   ├── storage/          # Storage adapters
│   └── transform/        # Data transformation
├── helm/                 # Kubernetes charts
├── Dockerfile
└── README.md
```

### Kubernetes Deployment

```yaml
# helm/values.yaml
replicaCount: 2

image:
  repository: acrtrading.azurecr.io/trader-data
  tag: latest

resources:
  requests:
    memory: "2Gi"
    cpu: "500m"
  limits:
    memory: "8Gi"
    cpu: "2000m"

# TimescaleDB sidecar for hot storage
timescaledb:
  enabled: true
  persistence:
    size: 100Gi
    storageClass: managed-premium

# Azure Blob for cold storage
azure:
  storageAccount: tradingdevstorage
  container: tick-data

# Exchange connectors
connectors:
  binance:
    enabled: true
  alpaca:
    enabled: true
    apiKey: ${ALPACA_API_KEY}
    apiSecret: ${ALPACA_API_SECRET}
```

### Ingress Configuration

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: trader-data
  annotations:
    kubernetes.io/ingress.class: azure/application-gateway
spec:
  rules:
  - host: data.trading.mindsightventures.ai
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: trader-data
            port:
              number: 8000
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
