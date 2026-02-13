# Trade Nexus Architecture

> 🏗️ Technical architecture for the AI Trading ecosystem

## Quick Overview

Trade Nexus is a **two-layer architecture**:

```
┌─────────────────────────────────────────┐
│            CLIENT LAYER                 │
│  Web UI │ API Direct │ OpenClaw Trader │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│         TRADE NEXUS PLATFORM            │
│                                         │
│  Agent Orchestrator (AI SDK v6)         │
│       │                                 │
│   ┌───┴───┬───────┬───────┐            │
│   ▼       ▼       ▼       ▼            │
│ Research Risk  Execution Data          │
│  Agent  Manager  Agent   Module        │
│                                         │
│  Knowledge Base │ Session Store        │
└─────────────────────────────────────────┘
```

## Architecture Documents

| Document | Description |
|----------|-------------|
| [AGENT_ARCHITECTURE.md](./AGENT_ARCHITECTURE.md) | Agent hierarchy, AI SDK patterns, sub-agents |
| [KNOWLEDGE_BASE.md](./KNOWLEDGE_BASE.md) | Supabase + pgvector for trading memory |
| [DATA_MODULE.md](./DATA_MODULE.md) | Market data providers (Alpaca, etc.) |
| [CLI_INTERFACE.md](./CLI_INTERFACE.md) | Command-line interface for agents |
| [OPENCLAW_INTEGRATION.md](./OPENCLAW_INTEGRATION.md) | OpenClaw Trader client agent |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Azure infrastructure (Container Apps + AKS) |

## Key Decisions

### Why Two Layers?

| Layer | Purpose |
|-------|---------|
| **Platform** | Multi-user, shared infrastructure, trading logic |
| **Client** | Personal interaction, memory, messaging |

### Why AI SDK for Platform?

| Concern | OpenClaw | AI SDK |
|---------|----------|--------|
| Multi-user | 1 instance per user 😬 | Shared instance ✅ |
| Sessions | Built-in (personal) | Custom (Supabase) ✅ |
| Control | Opinionated | Full flexibility ✅ |

### Why OpenClaw for Client?

For users who want **personal autonomous trading**:

- ✅ Local memory (privacy)
- ✅ Telegram/WhatsApp integration
- ✅ Heartbeats (proactive alerts)
- ✅ Personal preferences

## Technology Stack

| Component | Technology |
|-----------|------------|
| **Agent Framework** | Vercel AI SDK v6 |
| **Model Gateway** | OpenRouter (unified access to all models) |
| **Models** | Configurable per agent (see below) |
| **Database** | Supabase (PostgreSQL + pgvector) |
| **Market Data** | Alpaca (stocks), Binance (crypto) |
| **Execution** | Lona API + Live Engine |
| **Infrastructure** | Azure (Container Apps + AKS) |

### Model Options (via OpenRouter)

| Model | Provider | Best For |
|-------|----------|----------|
| Grok 4 | xAI | Fast reasoning |
| Claude Sonnet 4.5 | Anthropic | Complex analysis |
| Claude Sonnet 4.5 (thinking) | Anthropic | Deep reasoning |
| GPT-5.2 | OpenAI | General tasks |
| MiniMax-01 | MiniMax | Fast, cost-effective |
| Kimi K2 | Moonshot | Long context |

Models are configurable per agent via environment variables.

## Agent Types

### Platform Agents (AI SDK)

Run on Trade Nexus servers, serve all users:

| Agent | Responsibility |
|-------|---------------|
| **Orchestrator** | Coordinate agents, manage sessions |
| **Research** | Market analysis, strategy discovery |
| **Risk** | Position sizing, exposure limits |
| **Execution** | Trade execution, paper/live |

### Client Agents (OpenClaw)

Run on user's machine, personal to each user:

| Agent | Responsibility |
|-------|---------------|
| **OpenClaw Trader** | Personal interface to Trade Nexus |

## Data Flow

```
User Message → Client (Web/OpenClaw) → Trade Nexus API
                                           │
                                           ▼
                                    Orchestrator
                                           │
                        ┌──────────────────┼──────────────────┐
                        ▼                  ▼                  ▼
                   Research            Risk               Execution
                     Agent            Manager               Agent
                        │                  │                  │
                        └──────────────────┼──────────────────┘
                                           │
                                           ▼
                                    Response → User
```

## Getting Started

1. **Read** [AGENT_ARCHITECTURE.md](./AGENT_ARCHITECTURE.md) for full agent details
2. **Understand** the [KNOWLEDGE_BASE.md](./KNOWLEDGE_BASE.md) for memory/context
3. **Review** [DEPLOYMENT.md](./DEPLOYMENT.md) for infrastructure setup

## Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Agent Architecture | ✅ Designed | AI SDK v6 patterns defined |
| Knowledge Base | 📝 Planned | Supabase tables TBD |
| Data Module | 📝 Planned | Alpaca first |
| Platform API | 🔜 TODO | REST + WebSocket |
| OpenClaw Trader | 🔜 Future | After platform stable |

## Open Questions

- [ ] How to handle real-time streaming from multiple data sources?
- [ ] Circuit breaker patterns for autonomous trading?
- [ ] Rate limiting per user for API?
- [ ] Billing model for platform usage?
