# OpenClaw Trader Integration

## Overview

**OpenClaw Trader** is an optional client product that allows users to run a personal autonomous trading assistant that connects to the Trade Nexus platform.

> **Note**: OpenClaw is NOT used for the platform itself. The platform uses AI SDK v6 for multi-tenant agent orchestration. OpenClaw Trader is a **client option** for users who want personal autonomy.

## Why Offer OpenClaw Trader?

| Feature | Web UI | API Direct | OpenClaw Trader |
|---------|--------|------------|-----------------|
| Personal memory | ❌ Server-side | ❌ None | ✅ Local |
| Telegram/WhatsApp | ❌ | ❌ | ✅ |
| Autonomous alerts | Limited | ❌ | ✅ Heartbeats |
| Privacy | Server | API keys only | ✅ Local data |
| Always-on | ✅ | ❌ | ✅ If running |

**Use case**: Users who want a "personal trading AI" that remembers their preferences, alerts them proactively, and works through their existing messaging apps.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              USER'S MACHINE                     │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │           OPENCLAW TRADER                 │  │
│  │                                           │  │
│  │  ┌─────────────────────────────────────┐  │  │
│  │  │ OpenClaw Gateway                    │  │  │
│  │  │  • Agent loop (Claude/Grok)         │  │  │
│  │  │  • Session management               │  │  │
│  │  │  • Heartbeats (proactive)           │  │  │
│  │  └─────────────────────────────────────┘  │  │
│  │                    │                      │  │
│  │  ┌─────────────────┴─────────────────┐   │  │
│  │  │        SKILLS                      │   │  │
│  │  │  • trade-nexus (uses CLI)          │   │  │
│  │  │  • research (local tools)          │   │  │
│  │  │  • alerts (notifications)          │   │  │
│  │  └───────────────────┬───────────────┘   │  │
│  │                      │                    │  │
│  │  ┌─────────────────────────────────────┐  │  │
│  │  │        CHANNELS                     │  │  │
│  │  │  • Telegram                         │  │  │
│  │  │  • WhatsApp                         │  │  │
│  │  │  • Discord                          │  │  │
│  │  └─────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────┘  │
│                         │                       │
│  ┌──────────────────────┴────────────────────┐  │
│  │              trading-cli                  │  │
│  │  (installed locally, wraps API)           │  │
│  └──────────────────────┬────────────────────┘  │
│                         │                       │
└─────────────────────────┼───────────────────────┘
                          │
                          ▼ (HTTPS)
              ┌───────────────────────┐
              │   TRADE NEXUS API     │
              │  api.trade-nexus.io   │
              └───────────────────────┘
```

**Key insight**: OpenClaw uses `trading-cli` locally, which talks to the Trade Nexus API. This gives us:
- Offline-capable commands (cached data)
- Consistent interface for humans and agents
- Easy skill implementation (just exec CLI commands)

## Installation Options

### Option 1: Skill Only

Add Trade Nexus as a skill to existing OpenClaw:

```bash
# Install skill
openclaw skills install trade-nexus/trader-skill

# Configure
openclaw configure
# → Set TRADE_NEXUS_API_KEY
```

### Option 2: Full Agent Template

Install pre-configured trading agent:

```bash
# Add agent from template
openclaw agents add trader --from trade-nexus/trader-agent

# This creates:
# ~/.openclaw/workspace-trader/
#   ├── AGENTS.md (trading-focused instructions)
#   ├── SOUL.md (trader personality)
#   └── skills/trade-nexus/
```

### Option 3: Docker (Headless)

Run as always-on service:

```bash
docker run -d \
  -e TRADE_NEXUS_API_KEY=xxx \
  -e TELEGRAM_BOT_TOKEN=xxx \
  -v ~/.openclaw-trader:/root/.openclaw \
  trade-nexus/openclaw-trader:latest
```

## Skill Specification

### SKILL.md

```yaml
name: trade-nexus
description: Personal trading assistant connected to Trade Nexus platform
version: 1.0.0

env:
  TRADE_NEXUS_API_URL:
    required: true
    default: https://api.trade-nexus.io
  TRADE_NEXUS_API_KEY:
    required: true
    description: Your Trade Nexus API key

commands:
  portfolio: Show portfolio status and P&L
  trade: Execute a trade
  research: Research market or strategy
  strategies: List, create, deploy, or stop strategies
  alerts: Configure price and portfolio alerts
  
read_when:
  - User asks about trading, portfolio, or market
  - User wants to execute trades
  - User asks about strategies or backtesting
```

### Tool Implementations (CLI-based)

The skill uses `trading-cli` commands, making it simple and consistent:

```typescript
// skills/trade-nexus/tools.ts
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Helper to run CLI commands
async function cli(command: string): Promise<string> {
  const { stdout, stderr } = await execAsync(`trading-cli ${command} --json`);
  if (stderr) throw new Error(stderr);
  return stdout;
}

export const tools = {
  // Portfolio
  getPortfolio: {
    description: 'Get current portfolio status',
    parameters: {},
    execute: async () => cli('portfolio status'),
  },
  
  getPortfolioHistory: {
    description: 'Get portfolio history',
    parameters: {
      days: { type: 'number', default: 30 },
    },
    execute: async ({ days }) => cli(`portfolio history --days ${days}`),
  },
  
  // Trading
  executeTrade: {
    description: 'Execute a trade',
    parameters: {
      symbol: { type: 'string', required: true },
      side: { type: 'string', enum: ['buy', 'sell'], required: true },
      quantity: { type: 'number', required: true },
      type: { type: 'string', enum: ['market', 'limit'], default: 'market' },
      price: { type: 'number' },
    },
    execute: async ({ symbol, side, quantity, type, price }) => {
      let cmd = `trade ${side} ${symbol} ${quantity}`;
      if (type === 'limit' && price) cmd += ` --limit ${price}`;
      return cli(cmd);
    },
  },
  
  // Research
  research: {
    description: 'Research market conditions or strategies',
    parameters: {
      query: { type: 'string', required: true },
    },
    execute: async ({ query }) => cli(`research "${query}"`),
  },
  
  sentiment: {
    description: 'Get sentiment analysis for an asset',
    parameters: {
      symbol: { type: 'string', required: true },
    },
    execute: async ({ symbol }) => cli(`research sentiment ${symbol}`),
  },
  
  // Strategies
  listStrategies: {
    description: 'List trading strategies',
    parameters: {
      status: { type: 'string', enum: ['all', 'active', 'stopped'], default: 'all' },
    },
    execute: async ({ status }) => cli(`strategy list --status ${status}`),
  },
  
  createStrategy: {
    description: 'Create a new trading strategy',
    parameters: {
      name: { type: 'string', required: true },
      description: { type: 'string', required: true },
    },
    execute: async ({ name, description }) => 
      cli(`strategy create "${name}" --description "${description}"`),
  },
  
  deployStrategy: {
    description: 'Deploy a strategy to paper/live trading',
    parameters: {
      strategyId: { type: 'string', required: true },
      mode: { type: 'string', enum: ['paper', 'live'], default: 'paper' },
    },
    execute: async ({ strategyId, mode }) => 
      cli(`strategy deploy ${strategyId} --mode ${mode}`),
  },
  
  backtestStrategy: {
    description: 'Backtest a strategy',
    parameters: {
      strategyId: { type: 'string', required: true },
      dataId: { type: 'string', required: true },
    },
    execute: async ({ strategyId, dataId }) => 
      cli(`strategy backtest ${strategyId} --data ${dataId}`),
  },
  
  // Data
  getCandles: {
    description: 'Get candlestick data',
    parameters: {
      symbol: { type: 'string', required: true },
      interval: { type: 'string', default: '1h' },
      limit: { type: 'number', default: 100 },
    },
    execute: async ({ symbol, interval, limit }) => 
      cli(`data candles ${symbol} ${interval} --limit ${limit}`),
  },
  
  getQuote: {
    description: 'Get current price quote',
    parameters: {
      symbol: { type: 'string', required: true },
    },
    execute: async ({ symbol }) => cli(`data quote ${symbol}`),
  },
};
```

**Why CLI instead of SDK?**
- Simpler implementation (just shell commands)
- Consistent with human usage
- Easier to test and debug
- Works offline with cached data
```

## Heartbeat Configuration

Configure proactive monitoring in OpenClaw:

```yaml
# ~/.openclaw/workspace-trader/HEARTBEAT.md

## Trading Heartbeat (every 5 minutes)

1. Check portfolio P&L
2. Check active strategy status
3. Check pending alerts

If significant change (>2% move, strategy signal, alert triggered):
  - Notify user via Telegram
  - Log to daily notes

Otherwise: HEARTBEAT_OK
```

## Agent Templates

### AGENTS.md (Trader)

```markdown
# Trading Agent

You are a personal trading assistant connected to Trade Nexus.

## Capabilities

- Portfolio management and monitoring
- Trade execution (paper/live)
- Strategy research and backtesting
- Market analysis

## Guidelines

- Always confirm before executing live trades
- Report P&L changes > 2%
- Explain risk before suggesting trades
- Use paper trading for testing strategies

## Tools

Use the trade-nexus skill for all trading operations.
```

### SOUL.md (Trader Personality)

```markdown
# Trader Persona

You're a thoughtful trading assistant. Not a gambler.

- Be data-driven, not emotional
- Always consider risk first
- Explain your reasoning
- Admit uncertainty when it exists
- Celebrate wins modestly, learn from losses

Tone: Professional but friendly. Like a good trading buddy.
```

## Example Interactions

### Portfolio Check

```
User (Telegram): How's my portfolio?

OpenClaw Trader:
  1. Calls getPortfolio()
  2. Adds personal context (user's goals, recent history)
  
Response: "Your portfolio is up 3.2% today ($1,240). 
          BTC leading at +5.1%. Your momentum strategy 
          triggered 2 buys this morning. Want details?"
```

### Trade Execution

```
User: Buy 0.1 ETH

OpenClaw Trader:
  1. Calls executeTrade({ symbol: 'ETH', side: 'buy', quantity: 0.1 })
  2. Confirms with user first (if live mode)
  
Response: "Executed: Bought 0.1 ETH at $2,340.50
          Total cost: $234.05
          New ETH position: 0.5 ETH"
```

### Proactive Alert (Heartbeat)

```
[Heartbeat triggers at 14:00]

OpenClaw Trader:
  1. Checks portfolio → BTC down 5%
  2. Exceeds threshold
  3. Sends alert
  
Telegram: "⚠️ Alert: BTC dropped 5% in the last hour.
          Your BTC position is now -$450.
          Current price: $42,100. Want me to analyze?"
```

## SDK for Skill Developers

We'll provide an SDK for building custom Trade Nexus skills:

```typescript
// @trade-nexus/sdk
import { TradeNexusClient } from '@trade-nexus/sdk';

const client = new TradeNexusClient({
  apiUrl: 'https://api.trade-nexus.io',
  apiKey: process.env.TRADE_NEXUS_API_KEY,
});

// Portfolio
await client.portfolio.get();
await client.portfolio.history({ days: 30 });

// Trading
await client.trade.execute({ symbol, side, quantity });
await client.trade.getOrder(orderId);

// Strategies
await client.strategies.list();
await client.strategies.create({ name, description });
await client.strategies.deploy(strategyId, { mode: 'paper' });
await client.strategies.backtest(strategyId, { dataId });

// Research
await client.research.query('BTC momentum analysis');
await client.research.sentiment('ETH');

// Data
await client.data.candles({ symbol, interval, limit });
await client.data.quote(symbol);
```

## Roadmap

| Phase | Milestone |
|-------|-----------|
| **Phase 1** | Platform API stable |
| **Phase 2** | SDK published (`@trade-nexus/sdk`) |
| **Phase 3** | OpenClaw skill (`trade-nexus/trader-skill`) |
| **Phase 4** | Full agent template |
| **Phase 5** | Docker image for headless deployment |
