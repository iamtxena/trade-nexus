# Architecture Review Brief

> **Purpose**: External architecture review of the Trade Nexus trading platform

---

## Overview

**Trade Nexus** is an AI-powered multi-agent trading platform that enables users to research, backtest, and execute trading strategies across crypto and stocks.

### Core Components

| Component | Description | Repo |
|-----------|-------------|------|
| **Trade Nexus** | Main platform: API, agents, web UI, CLI | `trade-nexus` |
| **Live Engine** | Real-time paper/live trade execution | `live-engine` |
| **Lona** | Strategy generation, backtesting, scoring | External (lona.agency) |
| **Data Module** | Market data ingestion, storage, filtering | `trader-data` (planned) |
| **Validation Layer** | JSON-first strategy validation, regression gates, optional trader review | `trade-nexus` (new wave) |

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLIENTS                                        │
│                                                                          │
│   ┌────────┐    ┌────────┐    ┌────────┐    ┌─────────────────┐         │
│   │ Web UI │    │  CLI   │    │  API   │    │ OpenClaw Trader │         │
│   │        │    │        │    │ Direct │    │   (optional)    │         │
│   └────┬───┘    └────┬───┘    └────┬───┘    └────────┬────────┘         │
│        │             │             │                  │                  │
│        └─────────────┴─────────────┴──────────────────┘                  │
│                                    │                                     │
└────────────────────────────────────┼─────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      TRADE NEXUS PLATFORM                                │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │              AGENT ORCHESTRATOR (AI SDK v6)                      │   │
│   │                                                                  │   │
│   │   Coordinates AI agents, manages per-user sessions               │   │
│   └──────────────────────────┬───────────────────────────────────────┘   │
│                              │                                           │
│          ┌───────────────────┼───────────────────┐                      │
│          ▼                   ▼                   ▼                      │
│   ┌────────────┐     ┌────────────┐     ┌────────────┐                  │
│   │  RESEARCH  │     │    RISK    │     │ EXECUTION  │                  │
│   │   AGENT    │     │  MANAGER   │     │   AGENT    │                  │
│   └────────────┘     └────────────┘     └────────────┘                  │
│                                                                          │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│   │ KNOWLEDGE BASE  │  │   DATA MODULE   │  │  PLATFORM API   │         │
│   │   (Supabase)    │  │   (Alpaca)      │  │                 │         │
│   └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│                                                                          │
└────────────────────────────────────────────────────────────────────────┘
                    │                              │
                    ▼                              ▼
┌──────────────────────────────┐  ┌──────────────────────────────┐
│           LONA               │  │        LIVE ENGINE           │
│                              │  │                              │
│  • Strategy generation       │  │  • Paper trading execution   │
│  • Backtesting               │  │  • Live trading execution    │
│  • Strategy scoring          │  │  • Position management       │
│  • Historical data storage   │  │  • Order routing             │
│                              │  │                              │
│  API: lona.agency            │  │  Repo: live-engine           │
└──────────────────────────────┘  └──────────────────────────────┘
```

---

## What We're Building

### 1. Multi-Agent Trading Intelligence (AI SDK v6)

Platform agents that coordinate trading decisions:

- **Orchestrator**: Routes requests, manages sessions
- **Research Agent**: Market analysis, strategy discovery, news sentiment
- **Risk Manager**: Position sizing, exposure limits, drawdown control
- **Execution Agent**: Trade execution via Live Engine

### 2. CLI-First Interface

The CLI (`trading-cli`) is the primary interface:
- Human use: `trading-cli portfolio status`
- Agent use: OpenClaw skill calls CLI commands
- Scriptable, testable, universal

### 3. Contextual Backtesting (News Correlation)

Strategies can access news/sentiment that was available at each candle:

```typescript
interface ContextualCandle {
  timestamp: number;
  open, high, low, close, volume: number;
  news: NewsItem[];     // News published BEFORE this candle
  sentiment: number;    // Aggregate sentiment (-1 to 1)
  regime: 'bull' | 'bear' | 'sideways';
}
```

This enables realistic backtesting where the agent has the same information it would have in live trading.

### 4. Two-Layer Architecture

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Platform** | AI SDK v6 + Supabase | Multi-tenant trading intelligence |
| **Client** | Web/CLI/OpenClaw | User interaction, personal preferences |

**Why not one agent per user?** Multi-tenant platforms need shared infrastructure. AI SDK gives us control over sessions while sharing resources.

### 5. Validation-First Trader Review (new)

Every strategy run should be validated through a JSON-first artifact that includes:

- prompt and generated strategy output,
- indicator declarations vs rendered indicator evidence,
- trades and execution-log evidence,
- data lineage and metric consistency checks,
- optional human trader review state.

HTML/PDF outputs are optional renderings derived from the same canonical JSON artifact. Merge/release gates are blocked on validation policy failures.

---

## Documents to Review

All architecture documents are in `docs/architecture/`:

| Document | What It Covers |
|----------|----------------|
| **[README.md](./architecture/README.md)** | Overview, parallel workstreams, quick start |
| **[TARGET_ARCHITECTURE_V2.md](./architecture/TARGET_ARCHITECTURE_V2.md)** | Canonical to-be architecture and boundaries |
| **[INTERFACES.md](./architecture/INTERFACES.md)** | v2 interface model (public API + adapter contracts) |
| **[API_CONTRACT_GOVERNANCE.md](./architecture/API_CONTRACT_GOVERNANCE.md)** | Contract-first workflow and change policy |
| **[GAP_ANALYSIS_ASIS_TOBE.md](./architecture/GAP_ANALYSIS_ASIS_TOBE.md)** | As-is to to-be gap closure plan |
| **[DELIVERY_PLAN_AND_TEAM_TOPOLOGY.md](./architecture/DELIVERY_PLAN_AND_TEAM_TOPOLOGY.md)** | Team structure, repo creation plan, and ticket sectors |
| **[DATA_LIFECYCLE_AND_LONA_CONNECTOR_V2.md](./architecture/DATA_LIFECYCLE_AND_LONA_CONNECTOR_V2.md)** | Large-file dataset lifecycle and non-invasive Lona publish connector |
| **[GATE_TEAM_EXECUTION_PLAYBOOK.md](./architecture/GATE_TEAM_EXECUTION_PLAYBOOK.md)** | Gate-by-gate execution model and team update templates |
| **[specs/platform-api.openapi.yaml](./architecture/specs/platform-api.openapi.yaml)** | Single source of truth API contract |
| **[AGENT_ARCHITECTURE.md](./architecture/AGENT_ARCHITECTURE.md)** | Agent design, AI SDK patterns, Lona/Live Engine integration |
| **[DATA_MODULE.md](./architecture/DATA_MODULE.md)** | Market data, news ingestion, contextual candles |
| **[KNOWLEDGE_BASE.md](./architecture/KNOWLEDGE_BASE.md)** | Supabase schema, vector search, patterns storage |
| **[CLI_INTERFACE.md](./architecture/CLI_INTERFACE.md)** | CLI commands, output formats |
| **[OPENCLAW_INTEGRATION.md](./architecture/OPENCLAW_INTEGRATION.md)** | Optional personal agent client |
| **[DEPLOYMENT.md](./architecture/DEPLOYMENT.md)** | Azure Container Apps + AKS strategy |

### Related Repos

| Repo | Description | Your Access |
|------|-------------|-------------|
| `trade-nexus` | Main platform | ✅ Full access |
| `live-engine` | Trade execution | ✅ Full access |
| `lona` | Strategy/backtest | ❌ No access (see docs below) |

### Lona Reference

Lona is an external service (lona.agency) for strategy generation and backtesting. Key concepts:

- **Strategy Generation**: NLP → trading code (Python/TypeScript)
- **Backtesting**: Run strategy against historical data
- **Custom Data**: Supports OHLCV + custom fields (news, sentiment, etc.)
- **Paper Trading**: Deploy strategies for simulated trading
- **Scoring**: Ranks strategies by Sharpe, returns, drawdown

API endpoints referenced in architecture docs (see INTERFACES.md for contracts).

---

## Review Focus Areas

Please evaluate:

### 1. Architecture Soundness
- Is the two-layer (Platform/Client) separation correct?
- Does the agent hierarchy make sense?
- Are the module boundaries appropriate?

### 2. Interface Design
- Are the API contracts in INTERFACES.md complete?
- Any missing endpoints or data types?
- Are the contracts sufficient for parallel development?

### 3. Integration Points
- Trade Nexus ↔ Lona integration (strategy generation, backtesting)
- Trade Nexus ↔ Live Engine integration (execution)
- Data Module ↔ Knowledge Base (news correlation)

### 4. Scalability Concerns
- Per-user sessions via Supabase
- Real-time data streaming
- Heartbeat/autonomous agents

### 5. Data Flow
- Is the contextual candle design (OHLCV + news) practical?
- News ingestion pipeline
- Knowledge Base retrieval during trading

### 6. Parallel Development
- Can the 5 workstreams truly run in parallel?
- Are mock implementations sufficient?
- Any hidden dependencies?

---

## Known Issues / Blockers

| Issue | Impact | Status |
|-------|--------|--------|
| Live Engine code conversion bug | All paper trading broken | [Issue #10](https://github.com/iamtxena/live-engine/issues/10) |
| Lona custom data | Need for news correlation | ✅ Will be supported |

---

## Questions to Answer

After reviewing, please provide feedback on:

1. **Gaps**: What's missing from the architecture?
2. **Risks**: What could break or not scale?
3. **Improvements**: Suggestions for the design
4. **Priorities**: What should we build first?
5. **Alternatives**: Better approaches for any component?

---

## How to Review

1. **Start with** `docs/architecture/README.md` for overview
2. **Deep dive** into `INTERFACES.md` for API contracts
3. **Review** agent design in `AGENT_ARCHITECTURE.md`
4. **Check** data flows in `DATA_MODULE.md` and `KNOWLEDGE_BASE.md`
5. **Note** any concerns, questions, or suggestions

Feel free to:
- Add comments directly to the docs
- Create GitHub issues for specific concerns
- Propose alternative designs

---

## Contact

For questions during review:
- Create issues in the respective repos
- Tag @iamtxena for clarification

---

*Thank you for taking the time to review this architecture!*
