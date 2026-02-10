# Nexus CLI — Agent Operations Guide

Unified CLI for AI-driven trading operations. One command to rule them all.

## Quick Start

```bash
cd trade-nexus/frontend
bun run nexus --help        # see all commands
bun run nexus status        # check system health
```

## Prerequisites

The CLI reads environment variables from `frontend/.env.local`. These must be set:

| Variable | Required For | How To Get |
|----------|-------------|------------|
| `LONA_AGENT_TOKEN` | All Lona commands | Run `bun run nexus register` |
| `LONA_AGENT_REGISTRATION_SECRET` | Registration only | Provided by Lona platform admin |
| `XAI_API_KEY` | research, news, report, adjust, pipeline | xAI console |
| `LIVE_ENGINE_URL` | deploy, portfolio, report, pipeline | Default: `https://live.lona.agency` |
| `LIVE_ENGINE_SERVICE_KEY` | deploy, portfolio, report, pipeline | Must match `SERVICE_API_KEY` on live-engine |

## Commands Reference

### System

```bash
# Health check all systems
bun run nexus status

# Register with Lona Gateway (first-time setup)
bun run nexus register
```

### Market Research

```bash
# AI market analysis for specific asset classes
bun run nexus research --assets crypto,stocks
bun run nexus research --assets forex --capital 200000
```

### Strategy Management

```bash
# List all strategies on Lona
bun run nexus strategy list

# Create a strategy from natural language
bun run nexus strategy create --description "RSI mean reversion on BTC 1h, buy when RSI < 30, sell when RSI > 70"

# Create with custom name and provider
bun run nexus strategy create --description "..." --name "BTC RSI Bounce" --provider xai

# Get strategy details
bun run nexus strategy get --id <strategy-id>

# View strategy Python code
bun run nexus strategy code --id <strategy-id>

# Run a backtest
bun run nexus strategy backtest \
  --id <strategy-id> \
  --data <data-id> \
  --start 2025-01-01 \
  --end 2025-06-01 \
  --capital 100000

# Score and rank strategies by backtest report IDs
bun run nexus strategy score --ids <report-id-1>,<report-id-2>,<report-id-3>
```

### Market Data

```bash
# List available symbols (your uploaded data)
bun run nexus data list

# List pre-loaded global symbols (US equities, forex)
bun run nexus data list --global

# Download from Binance and upload to Lona
bun run nexus data download \
  --symbol BTCUSDT \
  --interval 1h \
  --start 2025-01-01 \
  --end 2025-06-01
```

### Deploy to Paper Trading

```bash
# Deploy a Lona strategy to paper trading on live-engine
# This: fetches code → converts Python→TS → creates portfolio → starts strategy
bun run nexus deploy \
  --strategy-id <lona-strategy-id> \
  --capital 10000 \
  --asset btcusdt \
  --interval 1m

# List deployed strategies
bun run nexus deploy list

# Stop a running strategy
bun run nexus deploy stop --id <live-engine-strategy-id>

# View execution logs
bun run nexus deploy logs --id <live-engine-strategy-id>
```

### Portfolio Management

```bash
# List all paper portfolios
bun run nexus portfolio list

# Show portfolio details (positions, P&L)
bun run nexus portfolio show --id <portfolio-id>

# Execute a manual paper trade
bun run nexus portfolio trade \
  --portfolio-id <id> \
  --symbol btcusdt \
  --side buy \
  --quantity 0.5
```

### Intelligence

```bash
# AI news and sentiment analysis
bun run nexus news --assets crypto,stocks
bun run nexus news --strategy-id <id>    # news for a specific strategy's asset

# Daily trading report (aggregates all portfolios + strategies)
bun run nexus report daily

# Detailed report for one strategy
bun run nexus report strategy --id <live-engine-strategy-id>

# AI portfolio adjustment suggestions
bun run nexus adjust
bun run nexus adjust --portfolio-id <id>
```

### Full Pipeline

```bash
# Automated end-to-end: research → create → download → backtest → score → deploy
bun run nexus pipeline --assets crypto --capital 50000

# Customize: deploy top 5 strategies
bun run nexus pipeline --assets crypto,stocks --capital 100000 --top 5

# Pipeline without deployment (research + backtest only)
bun run nexus pipeline --assets crypto --skip-deploy
```

## Typical Agent Workflow

```bash
# 1. Check systems are up
bun run nexus status

# 2. Research markets
bun run nexus research --assets crypto

# 3. Create a strategy from the research insights
bun run nexus strategy create --description "Bollinger Band breakout on ETH 4h..."

# 4. Download market data for backtesting
bun run nexus data download --symbol ETHUSDT --interval 4h --start 2024-06-01 --end 2025-01-01

# 5. Backtest the strategy
bun run nexus strategy backtest --id <strategy-id> --data <data-id> --start 2024-06-01 --end 2025-01-01

# 6. If results are good, deploy to paper trading
bun run nexus deploy --strategy-id <strategy-id> --capital 10000

# 7. Monitor
bun run nexus portfolio list
bun run nexus report daily
bun run nexus news --assets crypto

# 8. Get AI adjustment suggestions
bun run nexus adjust

# Or just run the full pipeline in one shot:
bun run nexus pipeline --assets crypto --capital 50000
```

## Architecture

```
AI Agent
  │
  └── nexus CLI (Bun)
        │
        ├── Lona Gateway (gateway.lona.agency)
        │     ├── Strategy creation (AI code gen)
        │     ├── Backtesting engine
        │     └── Market data storage
        │
        ├── live-engine (live.lona.agency)
        │     ├── Paper/live trading
        │     ├── Strategy execution (Vercel cron)
        │     └── Python→TS code conversion
        │
        └── Grok AI (xai)
              ├── Market research
              ├── News/sentiment analysis
              └── Portfolio adjustment suggestions
```

## Scoring Formula

Strategies are scored on a 0–1 composite scale:

| Weight | Metric | Normalization |
|--------|--------|---------------|
| 40% | Sharpe Ratio | capped at 3.0 |
| 25% | Max Drawdown | inverted, capped at 50% |
| 20% | Win Rate | as percentage |
| 15% | Total Return | capped at 100% |

Only strategies scoring above **0.3** are eligible for deployment.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Missing required env vars` | Check `.env.local` has the required keys |
| `live-engine DOWN` | Verify `LIVE_ENGINE_URL` and that live.lona.agency is deployed |
| `Lona API error 401` | Token expired — run `bun run nexus register` to get a new one |
| `live-engine API error 401` | `LIVE_ENGINE_SERVICE_KEY` doesn't match `SERVICE_API_KEY` on live-engine |
| Backtest timeout | Increase wait time or check Lona Gateway status |
