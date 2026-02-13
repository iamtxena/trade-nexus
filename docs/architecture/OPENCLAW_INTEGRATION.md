# OpenClaw Integration

## Overview

Deploy Trading Agent and Research Agent as OpenClaw bots for:
- Persistent memory across sessions
- Telegram/Slack/WhatsApp interface
- Access to existing tools and skills
- Heartbeat-based proactive monitoring
- Human oversight and control

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              OPENCLAW DEPLOYMENT                                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌───────────────────────────────────────────────────────────────────────────┐     │
│   │                         MESSAGE CHANNELS                                   │     │
│   │                                                                            │     │
│   │   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐           │     │
│   │   │ Telegram │    │  Slack   │    │ WhatsApp │    │   CLI    │           │     │
│   │   └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘           │     │
│   │        │               │               │               │                  │     │
│   │        └───────────────┴───────────────┴───────────────┘                  │     │
│   │                                   │                                        │     │
│   └───────────────────────────────────┼────────────────────────────────────────┘     │
│                                       │                                              │
│                                       ▼                                              │
│   ┌───────────────────────────────────────────────────────────────────────────┐     │
│   │                         OPENCLAW GATEWAY                                   │     │
│   │                                                                            │     │
│   │   • Message routing                                                        │     │
│   │   • Session management                                                     │     │
│   │   • Tool/skill dispatch                                                    │     │
│   │   • Heartbeat scheduler                                                    │     │
│   │                                                                            │     │
│   └───────────────────────────────────────────────────────────────────────────┘     │
│                                       │                                              │
│               ┌───────────────────────┴───────────────────────┐                     │
│               │                                               │                     │
│               ▼                                               ▼                     │
│   ┌───────────────────────────────┐           ┌───────────────────────────────┐    │
│   │       TRADING AGENT           │           │       RESEARCH AGENT          │    │
│   │       (OpenClaw Bot)          │           │       (OpenClaw Bot)          │    │
│   │                               │           │                               │    │
│   │   Model: grok-2-latest        │           │   Model: grok-2-latest        │    │
│   │                               │           │                               │    │
│   │   Skills:                     │           │   Skills:                     │    │
│   │   • trader-cli                │◀─────────▶│   • exa-search                │    │
│   │   • knowledge-base            │  sessions │   • x-search                  │    │
│   │   • portfolio-manager         │   _send   │   • firecrawl                 │    │
│   │                               │           │   • research-agent            │    │
│   │   Memory:                     │           │   • lona-backtest             │    │
│   │   • MEMORY.md                 │           │                               │    │
│   │   • memory/YYYY-MM-DD.md      │           │   Memory:                     │    │
│   │                               │           │   • research-history.md       │    │
│   └───────────────────────────────┘           └───────────────────────────────┘    │
│               │                                               │                     │
│               └───────────────────────┬───────────────────────┘                     │
│                                       │                                              │
│                                       ▼                                              │
│   ┌───────────────────────────────────────────────────────────────────────────┐     │
│   │                         SHARED INFRASTRUCTURE                              │     │
│   │                                                                            │     │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │     │
│   │   │    Lona      │  │ Live Engine  │  │  Knowledge   │  │    Data      │ │     │
│   │   │   Gateway    │  │              │  │    Base      │  │   Module     │ │     │
│   │   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │     │
│   │                                                                            │     │
│   └───────────────────────────────────────────────────────────────────────────┘     │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Trading Agent Configuration

### Directory Structure

```
~/.openclaw/
├── agents/
│   └── trading-agent/
│       ├── AGENTS.md           # Behavior instructions
│       ├── SOUL.md             # Personality
│       ├── MEMORY.md           # Long-term memory
│       ├── TOOLS.md            # Tool-specific notes
│       ├── HEARTBEAT.md        # Scheduled tasks
│       └── memory/
│           └── YYYY-MM-DD.md   # Daily notes
```

### AGENTS.md (Trading Agent)

```markdown
# Trading Agent

## Identity
You are a professional crypto/stocks trader managing a portfolio.
Your job is to make profitable trades while managing risk.

## Capabilities
- Research markets and discover strategies (via Research Agent)
- Execute paper/live trades (via trader-cli)
- Monitor portfolio and positions
- Query trading knowledge base
- Generate reports

## Daily Routine

### Morning (8:00 AM)
- Check overnight price movements
- Review any triggered trades
- Analyze market regime
- Plan day's strategy

### Market Hours
- Monitor positions
- Watch for entry/exit signals
- Respond to human queries

### Evening (8:00 PM)
- Generate daily report
- Update MEMORY.md with lessons
- Review strategy performance

## Risk Rules
- Never exceed 20% position size
- Always use stop losses
- Max daily loss: 5%
- Circuit breaker at 10% drawdown

## Communication
- Report significant trades to human immediately
- Daily summary to Telegram
- Ask for approval on live trades > $1000
```

### HEARTBEAT.md (Trading Agent)

```markdown
# Heartbeat Tasks

## Every 30 minutes (Market Hours)
- Check active positions for stop/target hits
- Evaluate strategy signals
- If signal: notify human with recommendation

## Every 4 hours
- Run `trader portfolio` check
- Update portfolio value in memory

## Daily 8:00 AM
- Run morning analysis
- Send daily briefing to Telegram

## Daily 8:00 PM
- Generate daily report
- Update MEMORY.md

## Weekly (Sunday 8:00 PM)
- Generate weekly performance report
- Review and update strategies
- Clean up old memory files
```

### Skills Configuration

Create a custom skill for trader-cli:

```
~/.openclaw/skills/trader-cli/
├── SKILL.md
└── (no additional files needed - CLI is installed globally)
```

**SKILL.md:**
```markdown
# Trader CLI Skill

## Description
Interface to the Trader Brain ecosystem via command line.

## Usage

The `trader` CLI accepts natural language commands:

```bash
# Research
trader research "momentum strategies for BTC"

# Portfolio
trader portfolio --json

# Trading
trader trade "buy 0.1 BTC at market" --dry-run

# Strategy
trader strategy backtest --id <id> --data <data-id>
```

## Output Parsing
Always use `--json` flag when you need to parse the output.

## Authentication
CLI uses environment variables:
- LONA_AGENT_TOKEN
- XAI_API_KEY
- LIVE_ENGINE_SERVICE_KEY

These should be set in ~/.openclaw/.env
```

## Research Agent Configuration

### AGENTS.md (Research Agent)

```markdown
# Research Agent

## Identity
You are a financial research analyst specializing in trading strategies.
You help the Trading Agent discover and validate trading opportunities.

## Capabilities
- Web search for market news (exa-search)
- Social media sentiment (x-search)
- Deep web scraping (firecrawl)
- Strategy backtesting (Lona)
- Knowledge base queries

## Research Process

1. **Understand Request**: What is being researched?
2. **Gather Data**: Use appropriate tools
3. **Analyze**: Synthesize findings
4. **Validate**: Backtest if strategy-related
5. **Report**: Structured summary with recommendations

## Output Format

Always return research in this structure:
```json
{
  "topic": "...",
  "summary": "...",
  "findings": [...],
  "recommendations": [...],
  "confidence": 0.0-1.0,
  "sources": [...]
}
```

## Tools Priority
1. Knowledge Base first (fastest, most relevant)
2. Exa search for web content
3. X search for sentiment/news
4. Firecrawl for deep content
```

## Inter-Agent Communication

### Using sessions_send

Trading Agent can invoke Research Agent:

```typescript
// In Trading Agent's workflow
const researchResult = await sessions_send({
  label: "research-agent",
  message: "Research momentum strategies for sideways BTC market",
  timeoutSeconds: 120
});
```

### Shared Knowledge

Both agents can access the same Knowledge Base:

```bash
# Trading Agent
trader knowledge query "momentum strategies"

# Research Agent
trader knowledge add --pattern "..."
```

## Deployment Steps

### 1. Install trader-cli globally

```bash
cd trader-cli
bun install
bun link
```

### 2. Create Trading Agent

```bash
openclaw agent create trading-agent \
  --model grok-2-latest \
  --channel telegram \
  --skills trader-cli,knowledge-base
```

### 3. Create Research Agent

```bash
openclaw agent create research-agent \
  --model grok-2-latest \
  --skills exa-search,x-search,firecrawl,trader-cli
```

### 4. Configure channels

```yaml
# openclaw.yaml
agents:
  trading-agent:
    channels:
      - telegram:@trader_bot
    heartbeat:
      enabled: true
      interval: 30m
      
  research-agent:
    channels:
      - internal  # Only responds to sessions_send
```

### 5. Set environment variables

```bash
# ~/.openclaw/.env
LONA_AGENT_TOKEN=...
XAI_API_KEY=...
LIVE_ENGINE_SERVICE_KEY=...
EXA_API_KEY=...
```

## Example Interaction Flow

```
Human (Telegram): "Hey trader, find me a good strategy for BTC"

Trading Agent:
  → sessions_send to Research Agent:
    "Research profitable BTC strategies for current market (sideways, low vol)"
    
Research Agent:
  → exa-search: "bitcoin trading strategies 2026"
  → x-search: "@BTC trading strategy momentum"
  → knowledge: query("BTC", "sideways", "strategy")
  → Lona: backtest top 3 candidates
  → Returns structured research report

Trading Agent:
  → Formats research for human
  → Adds recommendation
  → Sends to Telegram:
  
"Based on research, here are 3 strategies for current BTC market:

1. **RSI Mean Reversion** (Backtest: +15%, Sharpe 1.2)
   - Buy RSI < 30, Sell RSI > 70
   - Best for sideways markets ✓

2. **Bollinger Breakout** (Backtest: +22%, Sharpe 0.9)
   - Higher returns but more volatile
   
3. **MACD Trend Follow** (Backtest: +8%, Sharpe 1.5)
   - Lower returns but consistent

My recommendation: #1 for current conditions.
Want me to deploy to paper trading?"