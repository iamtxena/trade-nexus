# CLI Interface Architecture

## Overview

The `trader-cli` is a standalone command-line interface for the entire trading ecosystem. It's designed to be:
- Usable by humans directly
- Operable by AI agents (like OpenClaw bots)
- The primary interface before a web UI exists

## Design Principles

1. **Natural Language First**: Commands accept natural language, not just flags
2. **AI-Friendly Output**: Structured output (JSON) for machine parsing
3. **Conversational Mode**: Optional REPL for multi-turn interactions
4. **Stateless Commands**: Each command is self-contained
5. **Composable**: Commands can be piped together

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              trader-cli                                              │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                         CLI PARSER                                           │   │
│   │                                                                              │   │
│   │   Modes:                                                                     │   │
│   │   1. Command mode:  trader research "momentum strategies for BTC"           │   │
│   │   2. Interactive:   trader --interactive                                    │   │
│   │   3. Pipe mode:     echo "check portfolio" | trader                         │   │
│   │                                                                              │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                           │
│                                          ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                         INTENT PARSER (AI)                                   │   │
│   │                                                                              │   │
│   │   Input: "find me momentum strategies that worked in sideways markets"      │   │
│   │   Output: {                                                                  │   │
│   │     command: "research",                                                    │   │
│   │     intent: "find_strategies",                                              │   │
│   │     params: {                                                               │   │
│   │       type: "momentum",                                                     │   │
│   │       regime: "sideways"                                                    │   │
│   │     }                                                                       │   │
│   │   }                                                                         │   │
│   │                                                                              │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                           │
│                                          ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                         COMMAND ROUTER                                       │   │
│   │                                                                              │   │
│   │   research  → Research Agent                                                │   │
│   │   trade     → Trading Agent (via Execution)                                 │   │
│   │   portfolio → Portfolio queries                                             │   │
│   │   data      → Data Module                                                   │   │
│   │   strategy  → Lona Gateway                                                  │   │
│   │   knowledge → Knowledge Base                                                │   │
│   │   config    → Local configuration                                           │   │
│   │                                                                              │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                           │
│                                          ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                         OUTPUT FORMATTER                                     │   │
│   │                                                                              │   │
│   │   Formats:                                                                   │   │
│   │   --json     Machine-readable JSON                                          │   │
│   │   --table    Human-readable tables                                          │   │
│   │   --plain    Plain text (default for interactive)                           │   │
│   │   --markdown Markdown for docs/reports                                      │   │
│   │                                                                              │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Command Structure

### Top-Level Commands

```bash
trader <command> [options] [natural language query]

Commands:
  research    Market research and strategy discovery
  trade       Execute trades (paper or live)
  portfolio   View and manage portfolio
  data        Fetch and filter market data
  strategy    Create, backtest, deploy strategies
  knowledge   Query the knowledge base
  report      Generate reports
  config      Configuration management
  chat        Interactive conversation mode

Global Options:
  --json      Output as JSON
  --verbose   Verbose output
  --dry-run   Preview without executing
  --help      Show help
```

### Natural Language Examples

```bash
# Research
trader research "what momentum strategies work for BTC in sideways markets"
trader research "analyze ETH price action this week"
trader research "find arbitrage opportunities in crypto"

# Trading
trader trade "buy 0.1 BTC at market"
trader trade "set stop loss at 95000 for my BTC position"
trader trade "close all losing positions"

# Portfolio
trader portfolio "show me my current positions"
trader portfolio "what's my total P&L this week"
trader portfolio "am I overexposed to crypto"

# Data
trader data "download BTC 4h candles for last 6 months"
trader data "filter days where spread was under 0.1%"
trader data "show me volume profile for ETH today"

# Strategy
trader strategy "create a mean reversion strategy for BTC"
trader strategy "backtest my momentum strategy from Jan to Jun"
trader strategy "deploy best performing strategy to paper trading"

# Knowledge
trader knowledge "what strategies worked in the 2024 bull run"
trader knowledge "show me lessons from losing trades"
trader knowledge "what's the news sentiment for crypto today"
```

### Structured Commands (for scripting)

```bash
# Explicit command syntax
trader research --type momentum --asset BTC --regime sideways
trader trade --action buy --symbol BTCUSDT --quantity 0.1 --type market
trader portfolio --show positions --format json
trader data download --symbol BTCUSDT --interval 4h --start 2024-01-01 --end 2024-06-01
trader strategy backtest --id abc123 --data def456
```

## Interactive Mode

```bash
$ trader chat

Welcome to Trader Brain 🧠
Type 'help' for commands, 'exit' to quit.

You: What's the market looking like today?

Trader: Based on my analysis:
• BTC: $97,250 (+1.2%) - Consolidation, RSI neutral at 52
• ETH: $3,450 (+2.1%) - Outperforming BTC, approaching resistance
• Market regime: Sideways with low volatility

My mean reversion strategy is waiting for entry (RSI < 30).
No active positions.

You: Research some breakout strategies in case BTC breaks 100k

Trader: Researching breakout strategies for BTC above $100k...

Found 3 promising approaches:
1. Donchian Channel Breakout (20-period)
   - Historical win rate: 45%
   - Avg profit factor: 1.8
   
2. Volume-Confirmed Breakout
   - Requires 2x average volume on break
   - Better win rate (52%) but fewer signals
   
3. ATR Volatility Expansion
   - Triggers when ATR > 1.5x average
   - Good for catching big moves

Want me to backtest any of these?

You: Backtest the volume-confirmed one from October to now

Trader: Running backtest...
[Progress: ████████████████████] 100%

Results for "Volume-Confirmed Breakout" (Oct 2025 - Feb 2026):
• Total trades: 12
• Win rate: 58%
• Total return: +18.3%
• Max drawdown: -8.2%
• Sharpe ratio: 1.4

This scores 0.62 (above 0.3 threshold). Deploy to paper trading?

You: Yes, with $5000 capital

Trader: Deploying "Volume-Confirmed Breakout" to paper trading...
✅ Deployed! Strategy ID: xyz789
Capital: $5,000
Monitoring: BTCUSDT on 4H

I'll notify you when it takes a trade.

You: exit
Goodbye! 👋
```

## Output Formats

### JSON (for AI agents)

```bash
$ trader portfolio --json

{
  "success": true,
  "data": {
    "positions": [
      {
        "symbol": "BTCUSDT",
        "side": "long",
        "quantity": 0.15,
        "entryPrice": 95000,
        "currentPrice": 97250,
        "pnl": 337.50,
        "pnlPercent": 2.37
      }
    ],
    "cash": 8500,
    "totalValue": 22087.50,
    "dayPnl": 125.30,
    "dayPnlPercent": 0.57
  },
  "timestamp": "2026-02-13T15:00:00Z"
}
```

### Table (for humans)

```bash
$ trader portfolio

┌──────────────────────────────────────────────────────────────────┐
│                        PORTFOLIO SUMMARY                          │
├──────────────────────────────────────────────────────────────────┤
│ Total Value: $22,087.50        Day P&L: +$125.30 (+0.57%)        │
├──────────┬────────┬──────────┬───────────┬───────────┬──────────┤
│ Symbol   │ Side   │ Quantity │ Entry     │ Current   │ P&L      │
├──────────┼────────┼──────────┼───────────┼───────────┼──────────┤
│ BTCUSDT  │ LONG   │ 0.15     │ $95,000   │ $97,250   │ +$337.50 │
│          │        │          │           │           │ +2.37%   │
├──────────┴────────┴──────────┴───────────┴───────────┴──────────┤
│ Cash: $8,500.00                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Configuration

```yaml
# ~/.trader/config.yaml

# API endpoints
endpoints:
  lona: https://gateway.lona.agency
  live_engine: https://live.lona.agency
  knowledge: https://kb.trader.local
  data: https://data.trader.local

# API keys (or use environment variables)
auth:
  lona_token: ${LONA_AGENT_TOKEN}
  xai_key: ${XAI_API_KEY}
  
# Defaults
defaults:
  mode: paper  # paper | live
  output: table  # json | table | plain
  asset_class: crypto
  
# Risk limits
risk:
  max_position_size: 0.2  # 20% of portfolio
  max_daily_loss: 0.05    # 5% of portfolio
  circuit_breaker: 0.1    # 10% drawdown stops trading
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Runtime | Bun (TypeScript) |
| CLI Framework | Commander.js or Cliffy |
| AI Parser | AI SDK with Grok |
| HTTP Client | Built-in fetch |
| Output | chalk, cli-table3 |
| Config | cosmiconfig |
| Interactive | Inquirer.js or ink |

## Repository Structure

```
trader-cli/
├── src/
│   ├── index.ts           # Entry point
│   ├── parser/            # Natural language parser
│   ├── commands/          # Command implementations
│   │   ├── research.ts
│   │   ├── trade.ts
│   │   ├── portfolio.ts
│   │   ├── data.ts
│   │   ├── strategy.ts
│   │   ├── knowledge.ts
│   │   └── config.ts
│   ├── clients/           # API clients
│   │   ├── lona.ts
│   │   ├── live-engine.ts
│   │   ├── knowledge.ts
│   │   └── data.ts
│   ├── output/            # Formatters
│   │   ├── json.ts
│   │   ├── table.ts
│   │   └── markdown.ts
│   └── utils/
├── package.json
├── tsconfig.json
└── README.md
```

## Installation

```bash
# npm/bun global install
bun add -g @mindsightventures/trader-cli

# Or run directly
bunx @mindsightventures/trader-cli research "BTC momentum"

# Or clone and link
git clone https://github.com/mindsightventures/trader-cli
cd trader-cli
bun install
bun link
```
