# Trade Nexus

AI orchestrator connecting Lona (strategy generator/backtester) and Live Engine (real-time execution) with ML capabilities for autonomous trading.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Trade Nexus is the central orchestration layer for an autonomous trading system. It coordinates:

- **ML Predictions**: LSTM, sentiment analysis, volatility forecasting
- **Multi-Agent System**: Predictor, Anomaly Detection, Portfolio Optimization agents
- **Strategy Management**: Real-time strategy modification based on market conditions
- **Trade Execution**: Paper and live trading via integration with Live Engine

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Trade Nexus                               │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (Next.js 16)          │  Backend (FastAPI)            │
│  ├── Dashboard                  │  ├── ML Models                │
│  ├── Agent Management           │  │   ├── LSTM Predictor       │
│  ├── Strategy Monitoring        │  │   ├── Sentiment Analyzer   │
│  └── Portfolio Overview         │  │   └── Volatility Model     │
│                                 │  ├── LangGraph Agents         │
│  AI SDK v5 Agents:              │  │   ├── Predictor Agent      │
│  ├── Strategy Agent             │  │   ├── Anomaly Agent        │
│  ├── Decision Agent             │  │   └── Optimizer Agent      │
│  └── Orchestrator               │  └── API Endpoints            │
└─────────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
    ┌─────────┐                        ┌─────────────┐
    │  Lona   │◄──────MCP──────────────│ Live Engine │
    │ (Strat) │                        │ (Execution) │
    └─────────┘                        └─────────────┘
```

## Tech Stack

### Frontend
- **Runtime**: Bun
- **Framework**: Next.js 16 (App Router)
- **UI**: TailwindCSS v4, shadcn/ui
- **State**: TanStack Query v5, Zustand
- **AI**: AI SDK v5 with xAI Grok

### Backend
- **Package Manager**: uv
- **API**: FastAPI + Uvicorn
- **ML**: PyTorch, scikit-learn, pandas
- **Agents**: LangGraph / LangChain

### Infrastructure
- **Auth**: Clerk
- **Database**: Supabase PostgreSQL
- **Cache**: Upstash Redis
- **Observability**: LangSmith

## Getting Started

### Prerequisites
- [Bun](https://bun.sh) >= 1.0
- [uv](https://github.com/astral-sh/uv) >= 0.4
- Python >= 3.11

### Frontend Setup

```bash
cd frontend
bun install
cp .env.example .env.local
# Edit .env.local with your credentials
bun dev
```

### Backend Setup

```bash
cd backend
uv sync
cp .env.example .env
# Edit .env with your credentials
uv run uvicorn src.main:app --reload
```

## Project Structure

```
trade-nexus/
├── frontend/          # Next.js 16 App (Bun)
│   ├── src/
│   │   ├── app/       # App Router pages
│   │   ├── components/# React components
│   │   ├── hooks/     # TanStack Query hooks
│   │   ├── stores/    # Zustand stores
│   │   ├── lib/       # Business logic & AI agents
│   │   └── types/     # TypeScript definitions
│   └── public/
│
├── backend/           # Python ML Backend (uv)
│   ├── src/
│   │   ├── api/       # FastAPI routes
│   │   ├── agents/    # LangGraph agents
│   │   ├── models/    # ML models
│   │   ├── services/  # Business logic
│   │   └── schemas/   # Pydantic models
│   ├── notebooks/     # Jupyter prototyping
│   └── tests/
│
└── docs/              # Documentation
```

## Agents

### TypeScript Agents (AI SDK v5)
- **Strategy Agent**: Generates and refines trading strategies
- **Decision Agent**: Makes buy/sell/hold decisions
- **Orchestrator**: Coordinates multi-agent workflows

### Python Agents (LangGraph)
- **Predictor Agent**: LSTM/Prophet forecasts
- **Anomaly Agent**: Detects market anomalies
- **Optimizer Agent**: Portfolio optimization

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/predict` | Get ML predictions |
| POST | `/api/anomaly` | Check for anomalies |
| POST | `/api/optimize` | Portfolio optimization |
| GET | `/api/health` | Health check |

## Environment Variables

See `.env.example` files in `frontend/` and `backend/` directories.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Related Projects

- [Lona](https://github.com/iamtxena/lona) - Trading strategy generator and backtester
- [Live Engine](https://github.com/iamtxena/live-engine) - Real-time market data and trade execution
