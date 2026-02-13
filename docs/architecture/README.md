# Trade Nexus Architecture

> 🏗️ Technical architecture for the AI Trading ecosystem

## 🚀 Parallel Development Plan

**Key insight**: Define interfaces first, then everyone can work in parallel!

### Workstreams (Can Run Simultaneously)

| # | Module | Owner | Dependencies | Estimated Time |
|---|--------|-------|--------------|----------------|
| **1** | **Live Engine Bug Fix** | ? | None (isolated repo) | 1-2 days |
| **2** | **Data Module** (`trader-data`) | ? | Only external APIs (Alpaca) | 1 week |
| **3** | **Knowledge Base Schema** | ? | Only Supabase | 2-3 days |
| **4** | **Platform API** | ? | Interfaces only (can use mocks) | 1 week |
| **5** | **CLI enhancements** | ? | Interfaces only (can use mocks) | 3-4 days |

### Dependency Graph

```
PARALLEL (no overlap):
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ 1. Live Engine   │  │ 2. Data Module   │  │ 3. Knowledge     │
│    Bug Fix       │  │    (trader-data) │  │    Base Schema   │
│                  │  │                  │  │                  │
│ Issue #10        │  │ Alpaca connector │  │ Supabase tables  │
│ Separate repo    │  │ News ingestion   │  │ pgvector setup   │
└──────────────────┘  └──────────────────┘  └──────────────────┘

AFTER INTERFACES DEFINED:
┌─────────────────────────────────────────────────────────────┐
│ 4. Platform API + 5. CLI                                    │
│                                                             │
│ Can develop against mocks while 2 & 3 are built             │
│ Connect to real implementations when ready                  │
└─────────────────────────────────────────────────────────────┘

LAST (needs platform stable):
┌─────────────────────────────────────────────────────────────┐
│ 6. Agent Orchestrator (AI SDK v6)                           │
│                                                             │
│ Needs: Platform API + Data Module + Knowledge Base          │
└─────────────────────────────────────────────────────────────┘
```

### How to Work in Parallel

1. **Read** [INTERFACES.md](./INTERFACES.md) — defines all contracts
2. **Use mocks** — each SDK has mock implementations
3. **Agree on types** — TypeScript types are the source of truth
4. **Test against mocks** — verify your module works with fake data
5. **Connect when ready** — swap mocks for real implementations

See [INTERFACES.md](./INTERFACES.md) for all API contracts and SDK interfaces.

---

## Quick Overview

Trade Nexus is a **two-layer architecture**:

```
┌──────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                         │
│                                                          │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌───────────────┐  │
│  │ Web UI │  │  CLI   │  │  API   │  │ OpenClaw      │  │
│  │        │  │        │  │ Direct │  │ Trader        │  │
│  └───┬────┘  └───┬────┘  └───┬────┘  └───────┬───────┘  │
│      │           │           │               │          │
│      │           │           │          (uses CLI)      │
│      └───────────┴───────────┴───────────────┘          │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                 TRADE NEXUS PLATFORM                     │
│                                                          │
│  Agent Orchestrator (AI SDK v6)                          │
│       │                                                  │
│   ┌───┴───┬───────┬───────┐                             │
│   ▼       ▼       ▼       ▼                             │
│ Research Risk  Execution Data                           │
│  Agent  Manager  Agent   Module                         │
│                                                          │
│  Knowledge Base │ Session Store                         │
└──────────────────────────────────────────────────────────┘
```

**The CLI (`trading-cli`) is the primary interface** - OpenClaw Trader uses it, and humans can use it directly too.

## Architecture Documents

| Document | Description |
|----------|-------------|
| [INTERFACES.md](./INTERFACES.md) | **Start here!** API contracts for parallel development |
| [AGENT_ARCHITECTURE.md](./AGENT_ARCHITECTURE.md) | Agent hierarchy, AI SDK patterns, sub-agents |
| [KNOWLEDGE_BASE.md](./KNOWLEDGE_BASE.md) | Supabase + pgvector for trading memory |
| [DATA_MODULE.md](./DATA_MODULE.md) | Market data providers (Alpaca, etc.) + news |
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
| **MiniMax M2.5** | MiniMax | Fast, cost-effective (newest) |
| **GLM-5** | Z.AI | Strong reasoning |
| Kimi K2 | Moonshot | Long context |

Models are configurable per agent via environment variables.

> OpenRouter IDs: `minimax/minimax-m2.5`, `z-ai/glm-5`

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

---

## News Correlation & Custom Data

**Key feature**: Strategies can be correlated with news context for realistic backtesting.

```
┌───────────────────────────────────────────────────────────────┐
│             CONTEXTUAL BACKTESTING                            │
│                                                               │
│   Traditional:    Candle → Strategy → Signal                  │
│                   (price only)                                │
│                                                               │
│   Contextual:     Candle + News + Sentiment → Strategy        │
│                   (what the agent would actually know)        │
│                                                               │
│   Example: BTC candle at 14:00                                │
│   ├── OHLCV: open=42000, close=42100, ...                    │
│   ├── News (published before 14:00):                         │
│   │   ├── "Fed signals rate pause" (sentiment: 0.7)          │
│   │   └── "Whale moves 10k BTC" (sentiment: -0.3)            │
│   ├── Aggregate sentiment: 0.2                                │
│   └── Regime: sideways, Volatility: medium                   │
│                                                               │
│   Strategy can use ALL this context for decisions             │
└───────────────────────────────────────────────────────────────┘
```

**Implementation path**:
1. Data Module ingests news + stores with timestamps
2. Builds `ContextualCandle[]` with news attached to each candle
3. Lona enhanced to accept custom data (or workaround via Knowledge Base)
4. Agent uses contextual data for backtesting and live decisions

See [DATA_MODULE.md](./DATA_MODULE.md) for news ingestion details.

---

## Open Questions

- [ ] How to handle real-time streaming from multiple data sources?
- [ ] Circuit breaker patterns for autonomous trading?
- [ ] Rate limiting per user for API?
- [ ] Billing model for platform usage?
- [ ] Who implements custom data in Lona? Or use Knowledge Base workaround?
