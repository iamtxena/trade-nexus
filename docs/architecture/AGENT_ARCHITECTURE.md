# Agent Architecture

## Overview

Trade Nexus uses a **two-layer architecture** that separates the platform (backend) from client interfaces. The platform handles all trading logic, while clients (including an optional OpenClaw-based trader agent) handle user interaction.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                         │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐    │
│  │  Web UI  │  │   API    │  │  OpenClaw Trader   │    │
│  │          │  │  direct  │  │  (pre-built agent) │    │
│  └────┬─────┘  └────┬─────┘  └─────────┬──────────┘    │
│       │             │                   │               │
│       │             │         Personal memory,          │
│       │             │         Telegram/WhatsApp,        │
│       │             │         autonomous heartbeats     │
└───────┴─────────────┴───────────────────┴───────────────┘
                      │
                      ▼ (Trade Nexus API)
┌─────────────────────────────────────────────────────────┐
│              TRADE NEXUS PLATFORM                       │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │           AGENT ORCHESTRATOR (AI SDK v6)          │  │
│  │                                                   │  │
│  │   • Per-user session management                   │  │
│  │   • Agent loop & coordination                     │  │
│  │   • Tool registry & routing                       │  │
│  │   • Autonomous cron/heartbeats                    │  │
│  └───────────────────┬───────────────────────────────┘  │
│                      │                                  │
│     ┌────────────────┼────────────────┐                │
│     ▼                ▼                ▼                │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐         │
│  │ RESEARCH │  │   RISK   │  │  EXECUTION   │         │
│  │  AGENT   │  │ MANAGER  │  │    AGENT     │         │
│  │ (AI SDK) │  │ (AI SDK) │  │  (AI SDK)    │         │
│  └──────────┘  └──────────┘  └──────────────┘         │
│                                                         │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │ KNOWLEDGE BASE  │  │   DATA MODULE   │              │
│  │ (Supabase)      │  │   (Alpaca)      │              │
│  └─────────────────┘  └─────────────────┘              │
└─────────────────────────────────────────────────────────┘
```

## Layer Responsibilities

### Client Layer

Handles user interaction and personal preferences. Multiple client types supported:

| Client Type | Description | Use Case |
|-------------|-------------|----------|
| **Web UI** | Browser-based dashboard | Visual portfolio management |
| **API Direct** | REST/WebSocket API | Custom integrations, bots |
| **OpenClaw Trader** | Pre-built OpenClaw agent | Personal autonomous trading assistant |

### Platform Layer (Trade Nexus)

The core trading intelligence. Handles:

- **Agent Orchestrator**: Coordinates all sub-agents
- **Per-user Sessions**: Each user has isolated state
- **Sub-agents**: Autonomous AI SDK agents (Research, Risk, Execution)
- **Knowledge Base**: Shared trading patterns and history
- **Data Module**: Market data from providers (Alpaca, etc.)

---

## Technology Stack

### Platform: AI SDK v6

All platform agents built with [Vercel AI SDK v6](https://sdk.vercel.ai/docs) for:

- Unified agent loop (`generateText` with tools)
- Multi-step reasoning (`maxSteps`)
- Streaming support
- Multi-model flexibility

**Why AI SDK instead of OpenClaw for the platform?**

| Concern | OpenClaw | AI SDK |
|---------|----------|--------|
| Multi-user | 1 instance per user (heavy) | Shared instance, per-user sessions |
| Sessions | Built-in (personal) | Custom (Supabase) |
| Autonomy | Built-in heartbeats | Custom cron jobs |
| Flexibility | Opinionated | Full control |

**Conclusion**: AI SDK + custom infrastructure for multi-tenant platform.

### Client: OpenClaw Trader (Optional)

For users who want a **personal autonomous agent** that connects to Trade Nexus:

```
┌─────────────────────────────────────────┐
│         USER'S MACHINE / SERVER         │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │       OPENCLAW TRADER             │  │
│  │                                   │  │
│  │  • Personal memory (local)        │  │
│  │  • Telegram/WhatsApp integration  │  │
│  │  • Autonomous heartbeats          │  │
│  │  • User preferences               │  │
│  │                                   │  │
│  │  Skills:                          │  │
│  │  └── trade-nexus-skill            │  │
│  │      (connects to platform API)   │  │
│  └───────────────────────────────────┘  │
│                    │                    │
└────────────────────┼────────────────────┘
                     │
                     ▼ (API calls)
          ┌─────────────────────┐
          │  TRADE NEXUS API    │
          └─────────────────────┘
```

**Benefits of OpenClaw Trader:**

1. **Personal Memory**: Trading history, preferences stored locally
2. **Messaging Integration**: Telegram, WhatsApp, Discord
3. **True Autonomy**: Heartbeats, proactive alerts
4. **Privacy**: Sensitive data stays on user's machine

---

## Agent Orchestrator

The central coordinator built with AI SDK v6.

### Core Implementation

```typescript
// agent-orchestrator.ts
import { generateText, tool } from 'ai';
import { xai } from '@ai-sdk/xai';
import { z } from 'zod';

interface UserContext {
  userId: string;
  sessionId: string;
  portfolio: Portfolio;
  preferences: UserPreferences;
}

export async function runOrchestrator(
  context: UserContext,
  message: string
) {
  // 1. Load user session from Supabase
  const session = await sessionManager.load(context.userId);
  
  // 2. Run AI SDK agent
  const result = await generateText({
    model: xai('grok-2-latest'),
    
    system: `You are a trading orchestrator managing a portfolio.
    
    User: ${context.userId}
    Portfolio Value: $${context.portfolio.totalValue}
    Active Strategies: ${context.portfolio.strategies.length}
    
    You coordinate sub-agents:
    - research: Market analysis and strategy discovery
    - risk: Position sizing and exposure management
    - execute: Trade execution (paper/live)
    - data: Market data queries
    - knowledge: Historical patterns and learnings
    
    Always check risk before executing. Report significant events.`,
    
    messages: session.history.concat({ role: 'user', content: message }),
    
    tools: {
      research: researchAgentTool,
      risk: riskManagerTool,
      execute: executionAgentTool,
      data: dataModuleTool,
      knowledge: knowledgeBaseTool,
    },
    
    maxSteps: 10,
  });
  
  // 3. Save updated session
  await sessionManager.save(context.userId, {
    ...session,
    history: result.messages,
  });
  
  return result;
}
```

### Session Management (Supabase)

```typescript
// session-manager.ts
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY!
);

export const sessionManager = {
  async load(userId: string): Promise<Session> {
    const { data } = await supabase
      .from('trading_sessions')
      .select('*')
      .eq('user_id', userId)
      .single();
    
    return data ?? createDefaultSession(userId);
  },
  
  async save(userId: string, session: Session): Promise<void> {
    await supabase
      .from('trading_sessions')
      .upsert({
        user_id: userId,
        history: session.history,
        state: session.state,
        updated_at: new Date().toISOString(),
      });
  },
};
```

### Autonomous Heartbeats (Cron)

```typescript
// heartbeat.ts
// Runs on schedule (e.g., every 5 minutes)

export async function tradingHeartbeat() {
  // Get users with active strategies
  const activeUsers = await supabase
    .from('users')
    .select('id, preferences')
    .eq('has_active_strategies', true);
  
  for (const user of activeUsers.data ?? []) {
    // Check if any alerts needed
    const result = await runOrchestrator(
      { userId: user.id, ... },
      'Check portfolio status and active strategies. Alert if action needed.'
    );
    
    // Send notifications if needed
    if (result.alerts.length > 0) {
      await notifyUser(user.id, result.alerts);
    }
  }
}
```

---

## Sub-Agents

Each sub-agent is autonomous and built with AI SDK. They can be invoked by the Orchestrator or run independently.

### Research Agent

**Purpose**: Market analysis, strategy discovery, news sentiment

```typescript
// research-agent.ts
import { generateText, tool } from 'ai';

export const researchAgent = async (query: string, context: ResearchContext) => {
  return await generateText({
    model: xai('grok-2-latest'),
    
    system: `You are a trading research analyst.
    
    Your tools:
    - webSearch: Semantic web search (Exa)
    - socialSearch: Twitter/X search
    - scrape: Web scraping (Firecrawl)
    - generateStrategy: Create trading strategy via Lona
    - backtest: Test strategy on historical data
    
    Provide actionable insights with data backing.`,
    
    prompt: query,
    
    tools: {
      webSearch: tool({
        description: 'Search web for trading insights',
        parameters: z.object({ query: z.string() }),
        execute: async ({ query }) => exaSearch(query),
      }),
      socialSearch: tool({
        description: 'Search Twitter/X for sentiment',
        parameters: z.object({ query: z.string(), days: z.number().default(7) }),
        execute: async ({ query, days }) => xSearch(query, days),
      }),
      scrape: tool({
        description: 'Scrape webpage for data',
        parameters: z.object({ url: z.string() }),
        execute: async ({ url }) => firecrawl(url),
      }),
      generateStrategy: tool({
        description: 'Generate trading strategy code',
        parameters: z.object({ description: z.string() }),
        execute: async ({ description }) => lonaApi.generateStrategy(description),
      }),
      backtest: tool({
        description: 'Backtest a strategy',
        parameters: z.object({ strategyId: z.string(), dataId: z.string() }),
        execute: async ({ strategyId, dataId }) => lonaApi.backtest(strategyId, dataId),
      }),
    },
    
    maxSteps: 5,
  });
};

// Export as tool for Orchestrator
export const researchAgentTool = tool({
  description: 'Research market conditions, analyze strategies, get sentiment',
  parameters: z.object({
    query: z.string().describe('Research question'),
    asset: z.string().optional().describe('Specific asset to focus on'),
  }),
  execute: async ({ query, asset }) => {
    const result = await researchAgent(
      asset ? `${query} (focus on ${asset})` : query,
      {}
    );
    return result.text;
  },
});
```

### Risk Manager

**Purpose**: Position sizing, exposure limits, drawdown control

```typescript
// risk-manager.ts
export const riskManager = async (action: RiskAction, context: RiskContext) => {
  return await generateText({
    model: xai('grok-2-latest'),
    
    system: `You are a risk manager for a trading portfolio.
    
    Current Portfolio:
    ${JSON.stringify(context.portfolio, null, 2)}
    
    Risk Parameters:
    - Max position size: ${context.limits.maxPositionPct}%
    - Max sector exposure: ${context.limits.maxSectorPct}%
    - Max drawdown: ${context.limits.maxDrawdownPct}%
    
    Your tools:
    - calculateSize: Kelly criterion position sizing
    - checkExposure: Current portfolio exposure
    - correlationMatrix: Asset correlations
    - var: Value at Risk calculation
    
    Be conservative. Protect capital first.`,
    
    prompt: `Action: ${action.type}\nDetails: ${JSON.stringify(action.params)}`,
    
    tools: {
      calculateSize: tool({
        description: 'Calculate position size using Kelly criterion',
        parameters: z.object({
          winRate: z.number(),
          avgWin: z.number(),
          avgLoss: z.number(),
          portfolioValue: z.number(),
        }),
        execute: async (params) => kellySize(params),
      }),
      checkExposure: tool({
        description: 'Check current portfolio exposure',
        parameters: z.object({}),
        execute: async () => calculateExposure(context.portfolio),
      }),
      correlationMatrix: tool({
        description: 'Get correlation matrix for assets',
        parameters: z.object({ symbols: z.array(z.string()) }),
        execute: async ({ symbols }) => getCorrelations(symbols),
      }),
      var: tool({
        description: 'Calculate Value at Risk',
        parameters: z.object({ confidence: z.number().default(0.95) }),
        execute: async ({ confidence }) => calculateVaR(context.portfolio, confidence),
      }),
    },
    
    maxSteps: 3,
  });
};
```

### Execution Agent

**Purpose**: Trade execution, order management, paper/live routing

```typescript
// execution-agent.ts
export const executionAgent = async (order: Order, context: ExecutionContext) => {
  return await generateText({
    model: xai('grok-2-latest'),
    
    system: `You are a trade execution agent.
    
    Mode: ${context.mode} (paper/live)
    
    Your tools:
    - placeOrder: Submit order to exchange
    - getOrderStatus: Check order status
    - cancelOrder: Cancel pending order
    - getPositions: Current positions
    
    Execute efficiently. Minimize slippage. Report all actions.`,
    
    prompt: `Execute: ${JSON.stringify(order)}`,
    
    tools: {
      placeOrder: tool({
        description: 'Place a trade order',
        parameters: z.object({
          symbol: z.string(),
          side: z.enum(['buy', 'sell']),
          quantity: z.number(),
          type: z.enum(['market', 'limit']).default('market'),
          price: z.number().optional(),
        }),
        execute: async (params) => {
          if (context.mode === 'paper') {
            return lonaApi.paperTrade(params);
          } else {
            return liveEngine.execute(params);
          }
        },
      }),
      getOrderStatus: tool({
        description: 'Get status of an order',
        parameters: z.object({ orderId: z.string() }),
        execute: async ({ orderId }) => getOrderStatus(orderId, context.mode),
      }),
      cancelOrder: tool({
        description: 'Cancel a pending order',
        parameters: z.object({ orderId: z.string() }),
        execute: async ({ orderId }) => cancelOrder(orderId, context.mode),
      }),
      getPositions: tool({
        description: 'Get current positions',
        parameters: z.object({}),
        execute: async () => getPositions(context.userId),
      }),
    },
    
    maxSteps: 3,
  });
};
```

---

## OpenClaw Trader (Client Product)

A pre-built OpenClaw agent for users who want personal autonomous trading.

### Installation

```bash
# Option 1: Add as OpenClaw skill
openclaw skills install trade-nexus/trader-skill

# Option 2: Full agent template
openclaw agents add trader --from trade-nexus/trader-agent
```

### Skill Configuration

```yaml
# ~/.openclaw/skills/trader/SKILL.md
name: trade-nexus
description: Connect to Trade Nexus trading platform

env:
  TRADE_NEXUS_API_URL: required
  TRADE_NEXUS_API_KEY: required

commands:
  - portfolio: Show portfolio status
  - trade: Execute a trade
  - research: Research a topic
  - strategies: List/manage strategies
  - alerts: Configure price alerts
```

### Skill Implementation

```typescript
// trader-skill/index.ts
import { TradeNexusClient } from '@trade-nexus/sdk';

const client = new TradeNexusClient({
  apiUrl: process.env.TRADE_NEXUS_API_URL!,
  apiKey: process.env.TRADE_NEXUS_API_KEY!,
});

export const tools = {
  portfolio: {
    description: 'Get portfolio status',
    execute: async () => client.getPortfolio(),
  },
  trade: {
    description: 'Execute a trade',
    parameters: { symbol: 'string', side: 'buy|sell', quantity: 'number' },
    execute: async (params) => client.trade(params),
  },
  research: {
    description: 'Research market or strategy',
    parameters: { query: 'string' },
    execute: async ({ query }) => client.research(query),
  },
  strategies: {
    description: 'List or manage strategies',
    parameters: { action: 'list|create|deploy|stop' },
    execute: async ({ action, ...params }) => client.strategies(action, params),
  },
};
```

### User Experience

```
User: What's my portfolio looking like?

OpenClaw Trader:
  1. Calls trade-nexus skill → portfolio
  2. Gets data from Trade Nexus API
  3. Formats response with local context
  
Response: "Your portfolio is up 3.2% today. BTC position +5.1%, 
          ETH -1.2%. The momentum strategy triggered 2 trades..."
```

---

## Data Flow Examples

### Human → Platform (Direct API)

```
Human (Web UI): "Research momentum strategies for BTC"
       │
       ▼
Trade Nexus API: POST /api/research
       │
       ▼
Agent Orchestrator: routes to Research Agent
       │
       ▼
Research Agent: 
  1. webSearch("BTC momentum strategies 2024")
  2. socialSearch("$BTC momentum")
  3. generateStrategy("BTC 4H momentum RSI crossover")
  4. backtest(strategy_id, btc_data_id)
       │
       ▼
Response: Strategy analysis + backtest results
```

### Human → OpenClaw → Platform

```
Human (Telegram): "How's my portfolio?"
       │
       ▼
OpenClaw Trader: receives message
       │
       ▼
trade-nexus skill: client.getPortfolio()
       │
       ▼
Trade Nexus API: GET /api/portfolio
       │
       ▼
Agent Orchestrator: queries positions, P&L
       │
       ▼
OpenClaw Trader: formats with personal context
       │
       ▼
Telegram: "Your portfolio is up 3.2%..."
```

### Autonomous (Heartbeat)

```
Cron Job (every 5 min): tradingHeartbeat()
       │
       ▼
Agent Orchestrator: checks active strategies
       │
       ▼
Risk Manager: validates positions
       │
       ▼
IF alert needed:
  - Notify via API webhook
  - OR push to user's OpenClaw (if connected)
```

---

## Summary

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| **Platform** | AI SDK v6 + Supabase | Multi-user trading intelligence |
| **Orchestrator** | AI SDK agent | Coordinate sub-agents, manage sessions |
| **Research Agent** | AI SDK agent | Market analysis, strategy discovery |
| **Risk Manager** | AI SDK agent | Position sizing, exposure control |
| **Execution Agent** | AI SDK agent | Trade execution, paper/live |
| **Data Module** | REST API | Market data (Alpaca, etc.) |
| **Knowledge Base** | Supabase + pgvector | Trading patterns, history |
| **OpenClaw Trader** | OpenClaw + skill | Personal autonomous client |
