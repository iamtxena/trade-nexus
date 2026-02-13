# Trade Nexus Agents

## Overview

Trade Nexus uses a multi-agent architecture with specialized agents for different trading tasks. Agents are implemented in both TypeScript (frontend) and Python (backend).

## TypeScript Agents (AI SDK v6)

Located in `frontend/src/lib/ai/`

> **Note**: Using AI SDK v6.x with `tool()` helper and zod schemas for type-safe tool definitions.

### Orchestrator

**Purpose:** Coordinates multi-agent workflows and manages task execution.

**Capabilities:**
- Route tasks to appropriate agents
- Manage agent dependencies
- Aggregate results
- Handle failures and retries

**Usage:**
```typescript
import { orchestrate } from '@/lib/ai/orchestrator';

const results = await orchestrate([
  { id: '1', type: 'predictor', context: {...}, critical: true, priority: 1 },
  { id: '2', type: 'strategy', context: {...}, critical: false, priority: 2 },
]);
```

### Strategy Agent

**Purpose:** Generates and modifies trading strategies based on market conditions.

**Input:**
- Current price and market data
- ML predictions
- Portfolio state
- News sentiment

**Output:**
- Strategy name
- Entry/exit conditions
- Risk parameters
- Confidence score

**Usage:**
```typescript
import { generateStrategy } from '@/lib/ai/strategy-agent';

const strategy = await generateStrategy({
  symbol: 'BTC',
  currentPrice: 50000,
  predictions: [...],
  portfolio: {...},
});
```

### Decision Agent

**Purpose:** Makes buy/sell/hold decisions based on strategy signals.

**Input:**
- Strategy signal
- ML predictions
- Current position
- Risk limits

**Output:**
- Action: BUY | SELL | HOLD
- Quantity
- Price
- Confidence
- Reasoning

**Usage:**
```typescript
import { makeDecision } from '@/lib/ai/decision-agent';

const decision = await makeDecision({
  symbol: 'BTC',
  strategySignal: 'buy',
  predictions: [...],
  currentPosition: {...},
  riskLimits: {...},
});
```

### Predictor Agent (Proxy)

**Purpose:** Calls the ML backend for predictions.

**Usage:**
```typescript
import { getPrediction, checkAnomaly, optimizePortfolio } from '@/lib/ai/predictor-agent';

const prediction = await getPrediction({
  symbol: 'BTC',
  predictionType: 'price',
  timeframe: '24h',
});
```

## Python Agents (LangGraph)

Located in `backend/src/agents/`

### Predictor Agent

**Purpose:** Generates ML-based price and trend predictions.

**Pipeline:**
1. **Analyze** - LLM analyzes market conditions
2. **Predict** - LSTM model generates prediction

**Usage:**
```python
from src.agents.graph import run_prediction_graph

result = await run_prediction_graph(
    symbol="BTC",
    prediction_type="price",
    timeframe="24h",
    features={"current_price": 50000},
)
```

### Anomaly Agent

**Purpose:** Detects unusual market conditions.

**Pipeline:**
1. **Detect** - Statistical anomaly detection (Z-score)
2. **Analyze** - LLM explains anomaly if detected

**Usage:**
```python
from src.agents.graph import run_anomaly_graph

result = await run_anomaly_graph(
    symbol="BTC",
    data=[100, 101, 102, 103, 150],  # Price data
)
```

### Optimizer Agent

**Purpose:** Recommends optimal portfolio allocation.

**Pipeline:**
1. **Analyze Portfolio** - LLM reviews holdings and predictions
2. **Optimize** - Calculate optimal allocations

**Usage:**
```python
from src.agents.graph import run_optimization_graph

result = await run_optimization_graph(
    holdings={"BTC": 1.0, "ETH": 10.0},
    predictions=[...],
)
```

## Agent State Types

### TypeScript Types
```typescript
interface AgentContext {
  symbol: string;
  currentPrice: number;
  priceHistory: number[];
  predictions: Prediction[];
  portfolio: PortfolioState;
}

interface AgentResult {
  taskId: string;
  type: AgentType;
  success: boolean;
  output?: string;
  error?: string;
  duration: number;
}
```

### Python Types
```python
class PredictorState(TypedDict):
    symbol: str
    prediction_type: str
    timeframe: str
    features: dict[str, float] | None
    analysis: str | None
    prediction: dict[str, Any] | None
    confidence: float
```

## Adding New Agents

### TypeScript Agent
1. Create file in `frontend/src/lib/ai/`
2. Use AI SDK v5 `generateText` or `streamText`
3. Add to orchestrator routing

```typescript
import { generateText } from 'ai';
import { xai } from '@ai-sdk/xai';
import { wrapAISDKModel } from 'langsmith/wrappers/vercel';

const model = wrapAISDKModel(xai('grok-2-latest'));

export async function newAgent(context: Context): Promise<Result> {
  const response = await generateText({
    model,
    system: 'You are a specialized agent...',
    prompt: buildPrompt(context),
  });
  return parseOutput(response.text);
}
```

### Python Agent
1. Create file in `backend/src/agents/`
2. Define state TypedDict
3. Implement pipeline functions
4. Add to `graph.py`

```python
from typing import TypedDict
from langchain_xai import ChatXAI

class NewAgentState(TypedDict):
    input: str
    result: str | None

class NewAgent:
    def __init__(self):
        self.llm = ChatXAI(model="grok-2-latest")

    async def process(self, state: NewAgentState) -> NewAgentState:
        response = await self.llm.ainvoke([...])
        state["result"] = response.content
        return state
```

## Best Practices

1. **Single Responsibility**: Each agent should do one thing well
2. **Idempotency**: Agents should be safe to retry
3. **Observability**: Use LangSmith for tracing
4. **Error Handling**: Graceful degradation on failures
5. **Testing**: Unit tests for each agent
