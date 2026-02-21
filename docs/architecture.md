# Trade Nexus Architecture

## Overview

Trade Nexus is an AI orchestrator for autonomous trading that connects Lona (strategy generator/backtester) with Live Engine (real-time execution) through ML-powered agents.

## Infrastructure

### Azure Resources (West Europe)

| Resource | Name | Type | Purpose |
|----------|------|------|---------|
| Resource Group | `trade-nexus` | Microsoft.Resources/resourceGroups | Container for all resources |
| Container Registry | `tradenexusacr` | Microsoft.ContainerRegistry/registries | Docker image storage |
| Container Apps Environment | `trade-nexus-env` | Microsoft.App/managedEnvironments | Serverless container hosting |
| Container App | `trade-nexus-backend` | Microsoft.App/containerApps | FastAPI backend service |
| Log Analytics Workspace | `workspace-tradenexus1Uq1` | Microsoft.OperationalInsights/workspaces | Logging and monitoring |

### Resource Diagram

```
                                    ┌─────────────────────────────────────────────┐
                                    │           Azure (West Europe)                │
                                    │                                              │
┌──────────────┐                    │  ┌─────────────────────────────────────┐    │
│   GitHub     │                    │  │     Container Apps Environment       │    │
│   Actions    │────deploy─────────▶│  │         trade-nexus-env              │    │
└──────────────┘                    │  │                                       │    │
       │                            │  │  ┌─────────────────────────────────┐ │    │
       │                            │  │  │   Container App                  │ │    │
       │ push                       │  │  │   trade-nexus-backend            │ │    │
       ▼                            │  │  │   ┌───────────────────────────┐  │ │    │
┌──────────────┐                    │  │  │   │  FastAPI + LangGraph      │  │ │    │
│   Container  │                    │  │  │   │  - Predictor Agent        │  │ │    │
│   Registry   │◀────────pull──────▶│  │  │   │  - Anomaly Agent          │  │ │    │
│tradenexusacr │                    │  │  │   │  - Optimizer Agent        │  │ │    │
└──────────────┘                    │  │  │   └───────────────────────────┘  │ │    │
                                    │  │  └─────────────────────────────────┘ │    │
                                    │  └─────────────────────────────────────┘    │
                                    └─────────────────────────────────────────────┘
                                                          │
                                                          │
                    ┌─────────────────────────────────────┼─────────────────────────────────────┐
                    │                                     │                                     │
                    ▼                                     ▼                                     ▼
           ┌──────────────┐                      ┌──────────────┐                      ┌──────────────┐
           │   Supabase   │                      │    xAI       │                      │  LangSmith   │
           │  PostgreSQL  │                      │    Grok      │                      │ Observability│
           └──────────────┘                      └──────────────┘                      └──────────────┘
```

## Application Architecture

### Frontend (Next.js 16)

```
frontend/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── (auth)/             # Clerk authentication routes
│   │   ├── (dashboard)/        # Protected dashboard
│   │   │   ├── agents/         # AI agents monitoring
│   │   │   ├── strategies/     # Trading strategies
│   │   │   ├── portfolio/      # Portfolio management
│   │   │   └── settings/       # User settings
│   │   └── api/                # API routes
│   ├── components/             # React components
│   │   ├── ui/                 # shadcn/ui components
│   │   ├── agents/             # Agent-specific components
│   │   ├── charts/             # TradingView, Recharts
│   │   └── dashboard/          # Dashboard widgets
│   ├── hooks/                  # TanStack Query hooks
│   ├── stores/                 # Zustand stores
│   ├── lib/                    # Business logic
│   │   ├── ai/                 # AI SDK agents
│   │   ├── supabase/           # Database client
│   │   └── redis/              # Cache client
│   └── types/                  # TypeScript definitions
```

**Key Technologies:**
- Runtime: Bun
- Framework: Next.js 16 (App Router)
- Auth: Clerk
- State: TanStack Query v5 (server), Zustand (client)
- UI: TailwindCSS v4, shadcn/ui
- Charts: TradingView, Recharts
- AI: AI SDK v6 with xAI Grok

### Backend (FastAPI)

```
backend/
├── src/
│   ├── agents/                 # LangGraph agents
│   │   ├── predictor.py        # Price prediction agent
│   │   ├── anomaly.py          # Anomaly detection agent
│   │   ├── optimizer.py        # Portfolio optimization agent
│   │   └── graph.py            # LangGraph orchestration
│   ├── models/                 # ML models
│   │   ├── lstm.py             # LSTM price predictor
│   │   ├── sentiment.py        # News sentiment analyzer
│   │   └── volatility.py       # Volatility forecaster
│   ├── api/                    # FastAPI routes
│   ├── services/               # Business logic
│   └── schemas/                # Pydantic models
├── notebooks/                  # Jupyter prototyping
└── tests/                      # Test suite
```

**Key Technologies:**
- Runtime: Python 3.11 (uv)
- Framework: FastAPI + Uvicorn
- ML: PyTorch, scikit-learn, pandas
- Agents: LangGraph, LangChain
- AI: xAI Grok (langchain-xai)
- Observability: LangSmith

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  Trade Nexus                                     │
│                                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │    Lona      │───▶│   Predictor  │───▶│   Anomaly    │───▶│  Optimizer   │  │
│  │  (Signals)   │    │    Agent     │    │    Agent     │    │    Agent     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                   │                   │           │
│         │                   ▼                   ▼                   ▼           │
│         │            ┌─────────────────────────────────────────────────┐        │
│         │            │              LangGraph Orchestrator              │        │
│         │            └─────────────────────────────────────────────────┘        │
│         │                                      │                                 │
│         ▼                                      ▼                                 │
│  ┌──────────────┐                      ┌──────────────┐                         │
│  │ Live Engine  │◀─────────────────────│   Decision   │                         │
│  │ (Execution)  │                      │    Output    │                         │
│  └──────────────┘                      └──────────────┘                         │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Deployment Pipeline

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Push to     │────▶│   Build      │────▶│   Push to    │────▶│  Deploy to   │
│  main branch │     │   Docker     │     │   ACR        │     │  Container   │
│              │     │   Image      │     │              │     │  Apps        │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

**GitHub Actions Workflow:**
1. Trigger: Push to `main` branch (backend changes)
2. Build: Multi-stage Docker build
3. Push: Tag with commit SHA + `latest`
4. Deploy: Update Azure Container App

## Production Deployment

**Backend URL**: https://api-nexus.lona.agency/

**Health Check**: `GET /health`

### Scaling Configuration

| Setting | Value |
|---------|-------|
| Min Replicas | 0 (scale to zero) |
| Max Replicas | 3 |
| CPU | 2 vCPU |
| Memory | 4 GB |
| Port | 8000 |
| Ingress | External |

## External Services & Environment Variables

| Service | Purpose | Env Var | Secret? |
|---------|---------|---------|---------|
| xAI | Grok LLM | `XAI_API_KEY` | Yes |
| Supabase | PostgreSQL + pgvector | `SUPABASE_URL`, `SUPABASE_KEY` | Yes |
| LangSmith | Agent observability | `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | Yes |
| Lona Gateway | Strategy generation | `LONA_GATEWAY_URL`, `LONA_AGENT_TOKEN`, `LONA_AGENT_ID` | Partial |
| Live Engine | Trade execution | `LIVE_ENGINE_URL` | No |
| Clerk | Authentication (frontend) | `NEXT_PUBLIC_CLERK_*`, `CLERK_SECRET_KEY` | Yes |

## Security

- All secrets stored as Azure Container App secrets
- Service Principal with minimal permissions (Contributor on resource group only)
- HTTPS-only ingress
- Admin-enabled ACR for CI/CD (consider switching to managed identity for production)
