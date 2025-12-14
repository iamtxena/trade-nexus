# Trade Nexus Architecture

## System Overview

Trade Nexus is an AI orchestrator that connects multiple trading systems to enable autonomous trading with ML capabilities.

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Trade Nexus                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────┐          ┌─────────────────────┐          │
│  │   Frontend (Next.js) │          │   Backend (FastAPI)  │          │
│  │                      │   HTTP   │                      │          │
│  │  - Dashboard         │◄────────►│  - ML Models         │          │
│  │  - Agent Management  │          │  - LangGraph Agents  │          │
│  │  - AI SDK v5 Agents  │          │  - API Endpoints     │          │
│  └──────────┬───────────┘          └──────────┬───────────┘          │
│             │                                  │                      │
└─────────────┼──────────────────────────────────┼──────────────────────┘
              │                                  │
              │                                  │
    ┌─────────▼───────────┐          ┌──────────▼──────────┐
    │    External APIs     │          │      Databases       │
    │                      │          │                      │
    │  - Lona (MCP)        │          │  - Supabase          │
    │  - Live Engine       │          │  - Redis (Upstash)   │
    │  - Market Data       │          │                      │
    └──────────────────────┘          └──────────────────────┘
```

## Data Flow

### 1. Data Ingestion
```
Market Data APIs ──► Live Engine ──► Trade Nexus ──► ML Processing
       │                                    │
       └──────────► Redis Cache ◄───────────┘
```

### 2. Prediction Pipeline
```
Raw Data ──► Feature Engineering ──► ML Model ──► Prediction
                                         │
                                         ▼
                              LLM Enhancement (Grok)
                                         │
                                         ▼
                              Strategy Generation
```

### 3. Trading Decision Flow
```
Strategy Signal ──► Decision Agent ──► Risk Check ──► Execute/Reject
        │                                    │
        └────────── ML Predictions ──────────┘
```

## Component Details

### Frontend (Next.js 16)

**Tech Stack:**
- Bun runtime
- TailwindCSS v4
- TanStack Query v5 for server state
- Zustand for client state
- AI SDK v5 for TypeScript agents

**Key Components:**
- `Orchestrator`: Coordinates multi-agent workflows
- `StrategyAgent`: Generates trading strategies
- `DecisionAgent`: Makes trade decisions

### Backend (FastAPI)

**Tech Stack:**
- uv package manager
- PyTorch for ML models
- LangGraph for agent orchestration
- LangChain for LLM interactions

**Key Components:**
- `PredictorAgent`: LSTM/Prophet forecasts
- `AnomalyAgent`: Anomaly detection
- `OptimizerAgent`: Portfolio optimization

## Agent Architecture

### Multi-Agent System

```
┌────────────────────────────────────────────────────────┐
│                     Orchestrator                        │
├────────────────────────────────────────────────────────┤
│                          │                              │
│  ┌────────────┐  ┌──────▼──────┐  ┌────────────┐      │
│  │  Predictor │  │   Strategy  │  │  Decision  │      │
│  │   Agent    │  │    Agent    │  │   Agent    │      │
│  └─────┬──────┘  └──────┬──────┘  └─────┬──────┘      │
│        │                │               │              │
│        └────────────────┼───────────────┘              │
│                         │                              │
│                  ┌──────▼──────┐                       │
│                  │    Trade    │                       │
│                  │  Execution  │                       │
│                  └─────────────┘                       │
└────────────────────────────────────────────────────────┘
```

### Agent Communication

Agents communicate through:
1. **Shared State**: Predictions and context passed between agents
2. **Event Bus**: Async events for real-time updates
3. **Database**: Persistent storage in Supabase

## Security Considerations

1. **API Authentication**: Clerk for user auth, API keys for service-to-service
2. **Database Security**: Row Level Security (RLS) in Supabase
3. **Trade Safety**: Paper trading mode by default
4. **Risk Limits**: Configurable position size and drawdown limits

## Scaling Strategy

1. **Horizontal Scaling**: Stateless services allow multiple instances
2. **Caching**: Redis for frequently accessed data
3. **Background Processing**: Async agents for heavy ML computations
4. **Database**: Supabase handles connection pooling

## Deployment Architecture

```
┌─────────────────┐     ┌─────────────────┐
│     Vercel      │     │  Azure/Railway  │
│   (Frontend)    │────►│   (ML Backend)  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
         ┌───────────▼───────────┐
         │      Supabase         │
         │  (PostgreSQL + Auth)  │
         └───────────────────────┘
```
