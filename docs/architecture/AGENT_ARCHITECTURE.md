# Agent Architecture

## Overview

The Trader Brain uses a hierarchical agent architecture where the **Trading Agent** is the main actor that orchestrates all other components.

## Agent Hierarchy

```
                    ┌─────────────────────────┐
                    │     TRADING AGENT       │
                    │     (Main Actor)        │
                    │                         │
                    │  Responsibilities:      │
                    │  • Make trade decisions │
                    │  • Manage portfolio     │
                    │  • Coordinate agents    │
                    │  • Report to human      │
                    └───────────┬─────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │   RESEARCH   │   │     RISK     │   │   EXECUTION  │
    │    AGENT     │   │   MANAGER    │   │    AGENT     │
    │              │   │              │   │              │
    │ • Market     │   │ • Position   │   │ • Place      │
    │   analysis   │   │   sizing     │   │   orders     │
    │ • Strategy   │   │ • Exposure   │   │ • Monitor    │
    │   discovery  │   │   limits     │   │   fills      │
    │ • News       │   │ • Drawdown   │   │ • Paper/Live │
    │   sentiment  │   │   control    │   │   switching  │
    └──────────────┘   └──────────────┘   └──────────────┘
            │                   │                   │
            ▼                   ▼                   ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │  TOOLS:      │   │  TOOLS:      │   │  TOOLS:      │
    │ • exa-search │   │ • Portfolio  │   │ • Lona API   │
    │ • x-search   │   │   calculator │   │ • Live Engine│
    │ • firecrawl  │   │ • Correlation│   │   API        │
    │ • research-  │   │   matrix     │   │ • Binance    │
    │   agent      │   │ • VaR model  │   │   (paper)    │
    └──────────────┘   └──────────────┘   └──────────────┘
```

## Technology Stack

### AI SDK v6 (Latest)

All agents built with Vercel AI SDK v6 for consistency.

**Key v6 Features:**
- `generateObject()` / `streamObject()` (no longer experimental)
- Better tool type inference
- Attachments support (files, images)
- `maxSteps` for multi-turn agent loops

```typescript
// Trading Agent (Main Actor) - AI SDK v6
import { generateText, tool } from 'ai';
import { xai } from '@ai-sdk/xai';
import { z } from 'zod';

const tradingAgent = async (context: TradingContext) => {
  const result = await generateText({
    model: xai('grok-2-latest'),
    system: `You are an expert trader managing a portfolio.
    
    You have access to these tools:
    - research: Get market analysis and strategy ideas
    - risk: Check position sizing and exposure limits  
    - execute: Place paper or live trades
    - knowledge: Query trading patterns and history
    - data: Fetch market data
    
    Always check risk before executing trades.
    Report significant decisions to the human.`,
    
    prompt: context.userMessage,
    
    tools: {
      research: tool({
        description: 'Research market conditions and strategies',
        parameters: z.object({
          query: z.string(),
          asset: z.string().optional(),
        }),
        execute: async ({ query, asset }) => researchAgent(query, asset),
      }),
      risk: tool({
        description: 'Check risk limits and position sizing',
        parameters: z.object({
          action: z.enum(['validate', 'size', 'exposure']),
          trade: z.object({
            symbol: z.string(),
            side: z.enum(['buy', 'sell']),
            quantity: z.number(),
          }).optional(),
        }),
        execute: async ({ action, trade }) => riskManager(action, trade),
      }),
      execute: tool({
        description: 'Execute a trade (paper or live)',
        parameters: z.object({
          symbol: z.string(),
          side: z.enum(['buy', 'sell']),
          quantity: z.number(),
          type: z.enum(['market', 'limit']).default('market'),
          price: z.number().optional(),
        }),
        execute: async (params) => executionAgent(params),
      }),
      knowledge: tool({
        description: 'Query trading knowledge base',
        parameters: z.object({
          query: z.string(),
          filters: z.record(z.string()).optional(),
        }),
        execute: async ({ query, filters }) => knowledgeBase.search(query, filters),
      }),
      data: tool({
        description: 'Fetch market data',
        parameters: z.object({
          symbol: z.string(),
          interval: z.string().default('1h'),
          limit: z.number().default(100),
        }),
        execute: async ({ symbol, interval, limit }) => dataModule.getCandles(symbol, interval, limit),
      }),
    },
    
    maxSteps: 10, // Allow multi-step reasoning
  });
  
  return result;
};
```

### OpenClaw Integration

Deploy agents as OpenClaw bots for:
- Persistent memory across sessions
- Access to existing tools/skills
- Telegram/Slack interface
- Heartbeat-based monitoring

```yaml
# OpenClaw config for Trading Agent
agent:
  name: "Trader"
  model: "grok-2-latest"
  skills:
    - trader-cli        # CLI interface to ecosystem
    - research-agent    # Your existing research tools
    - exa-search        # Semantic web search
    - x-search          # Twitter/X search
    - firecrawl         # Web scraping
```

## Agent Specifications

### 1. Trading Agent (Main Actor)

**Deployment**: OpenClaw bot

**Responsibilities**:
- Orchestrate all trading operations
- Make final BUY/SELL/HOLD decisions
- Manage portfolio allocation
- Communicate with human

**State**:
```typescript
interface TradingAgentState {
  portfolio: {
    positions: Position[];
    cash: number;
    totalValue: number;
  };
  activeStrategies: Strategy[];
  pendingOrders: Order[];
  conversationHistory: Message[];
}
```

**Tools**:
| Tool | Description | Implementation |
|------|-------------|----------------|
| research | Get market analysis | Calls Research Agent |
| risk | Check limits | Calls Risk Manager |
| execute | Place trades | Calls Lona/Live Engine |
| knowledge | Query patterns | Calls Knowledge Base |
| data | Fetch market data | Calls Data Module |
| report | Generate reports | Internal |

### 2. Research Agent

**Deployment**: OpenClaw bot OR tool within Trading Agent

**Responsibilities**:
- Market condition analysis
- Strategy discovery and backtesting
- News and sentiment analysis
- Competitive analysis

**Tools** (your existing tools):
| Tool | Purpose |
|------|---------|
| `exa-search-agent` | Semantic web search |
| `x-search-agent` | Twitter/X search |
| `firecrawl-agent` | Web scraping |
| `research-agent` | General research |
| Lona API | Strategy generation/backtest |

**Example Flow**:
```
Human: "Research momentum strategies for crypto"
          │
          ▼
Research Agent:
  1. exa-search: "momentum trading strategies cryptocurrency 2024"
  2. x-search: "crypto momentum $BTC $ETH"
  3. knowledge: query("momentum", "strategy_patterns")
  4. Lona: generate_strategy("momentum BTC 4H...")
  5. Lona: backtest(strategy_id, data_id)
  6. Return: Summary + top strategies + backtest results
```

### 3. Risk Manager

**Deployment**: Tool/function (no separate bot needed)

**Responsibilities**:
- Position sizing (Kelly criterion, fixed fractional)
- Exposure limits (max % per asset, sector)
- Drawdown control (circuit breakers)
- Correlation analysis

**Interface**:
```typescript
interface RiskManager {
  // Check if trade is allowed
  validateTrade(trade: TradeRequest): ValidationResult;
  
  // Calculate position size
  calculateSize(
    signal: Signal,
    portfolio: Portfolio,
    volatility: number
  ): number;
  
  // Check portfolio health
  checkExposure(portfolio: Portfolio): ExposureReport;
  
  // Emergency stop
  triggerCircuitBreaker(reason: string): void;
}
```

### 4. Execution Agent

**Deployment**: Tool (wraps Lona + Live Engine)

**Responsibilities**:
- Translate decisions to orders
- Route to paper or live
- Monitor fills
- Handle errors/retries

**Interface**:
```typescript
interface ExecutionAgent {
  // Place order
  execute(order: Order): ExecutionResult;
  
  // Get status
  getOrderStatus(orderId: string): OrderStatus;
  
  // Cancel order
  cancel(orderId: string): boolean;
  
  // Switch mode
  setMode(mode: 'paper' | 'live'): void;
}
```

## Communication Patterns

### Human ↔ Trading Agent

```
Human: "What's the portfolio status?"
Trading Agent: 
  1. Fetch positions from Live Engine
  2. Calculate P&L
  3. Format report
  4. Reply to human