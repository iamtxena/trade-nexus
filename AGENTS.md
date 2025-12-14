# Trade Nexus - Development Guidelines

AI orchestrator connecting Lona (strategy generator/backtester) and Live Engine (real-time execution) with ML capabilities for autonomous trading.

## Repository

- **GitHub**: https://github.com/iamtxena/trade-nexus
- **License**: MIT

## Tech Stack

### Frontend (TypeScript)
- **Runtime**: Bun
- **Framework**: Next.js 16 (App Router)
- **UI**: TailwindCSS v4, shadcn/ui
- **State**: TanStack Query v5 (server state), Zustand (client state)
- **Charts**: TradingView lightweight-charts, Recharts
- **AI**: AI SDK v5 with xAI Grok
- **Auth**: Clerk
- **Database**: Supabase
- **Cache**: Upstash Redis
- **Observability**: LangSmith

### Backend (Python)
- **Package Manager**: uv
- **API**: FastAPI + Uvicorn
- **ML**: PyTorch, scikit-learn, pandas, numpy
- **Agents**: LangGraph, LangChain
- **AI Provider**: xAI Grok via langchain-xai

---

## Common Commands

### Frontend
```bash
cd frontend
bun dev          # Start development server
bun build        # Build for production
bun start        # Start production server
bun lint         # Run ESLint
bun typecheck    # Run TypeScript check
```

### Backend
```bash
cd backend
uv run uvicorn src.main:app --reload  # Start dev server
uv run pytest                          # Run tests
uv run python -m src.main              # Alternative start
```

---

## Architecture

### Directory Structure

```
trade-nexus/
├── frontend/                    # Next.js 16 App (Bun)
│   ├── src/
│   │   ├── app/
│   │   │   ├── (auth)/          # Clerk auth routes
│   │   │   ├── (dashboard)/     # Protected dashboard routes
│   │   │   │   ├── agents/      # Agent management
│   │   │   │   ├── strategies/  # Strategy monitoring
│   │   │   │   ├── portfolio/   # Portfolio overview
│   │   │   │   └── settings/    # Configuration
│   │   │   └── api/             # API routes
│   │   ├── components/
│   │   │   ├── ui/              # shadcn/ui components
│   │   │   ├── agents/          # Agent-specific components
│   │   │   ├── charts/          # Trading chart components
│   │   │   └── dashboard/       # Dashboard widgets
│   │   ├── hooks/               # TanStack Query hooks (use-*.ts)
│   │   ├── stores/              # Zustand stores (*-store.ts)
│   │   ├── lib/
│   │   │   ├── ai/              # AI agents and orchestration
│   │   │   ├── supabase/        # Database client
│   │   │   └── redis/           # Cache client
│   │   └── types/               # TypeScript definitions
│   └── public/
│
├── backend/                     # Python ML Backend (uv)
│   ├── src/
│   │   ├── api/                 # FastAPI routes and deps
│   │   ├── agents/              # LangGraph agents
│   │   │   ├── predictor.py     # Price prediction agent
│   │   │   ├── anomaly.py       # Anomaly detection agent
│   │   │   ├── optimizer.py     # Portfolio optimization agent
│   │   │   └── graph.py         # LangGraph orchestration
│   │   ├── models/              # ML models
│   │   │   ├── lstm.py          # LSTM price predictor
│   │   │   ├── sentiment.py     # News sentiment analyzer
│   │   │   └── volatility.py    # Volatility forecaster
│   │   ├── services/            # Business logic
│   │   └── schemas/             # Pydantic models
│   ├── notebooks/               # Jupyter prototyping
│   └── tests/
│
└── docs/                        # Documentation
```

---

## Development Guidelines

### TypeScript Rules

1. **Imports at top of file** - Never create imports in the middle of code
2. **Strict mode** - All TypeScript in strict mode
3. **No `any`** - Use proper types, `unknown` if truly needed
4. **Named exports** - Prefer named over default exports

### React/Next.js Patterns

1. **Server Components by default** - Only add `'use client'` when needed
2. **No `useEffect` for data** - Use TanStack Query for all data fetching
3. **Zustand for client state** - UI state, form state, local preferences
4. **Route groups** - Use `(auth)`, `(dashboard)` for organization

### State Management

```typescript
// TanStack Query for server state
export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: () => fetchAgents(),
  });
}

// Zustand for client state
export const useSettingsStore = create<SettingsState>((set) => ({
  theme: 'dark',
  setTheme: (theme) => set({ theme }),
}));
```

### AI SDK v5 Pattern (TypeScript)

```typescript
import { generateText } from 'ai';
import { xai } from '@ai-sdk/xai';

export async function strategyAgent(context: StrategyContext) {
  const result = await generateText({
    model: xai('grok-2-latest'),
    system: `You are a trading strategy agent. Analyze market conditions
             and suggest strategy modifications.`,
    prompt: buildPrompt(context),
  });
  return result.text;
}
```

### LangGraph Pattern (Python)

```python
from langgraph.graph import StateGraph, END
from langchain_xai import ChatXAI

def create_predictor_graph():
    graph = StateGraph(PredictorState)
    graph.add_node("analyze", analyze_market)
    graph.add_node("predict", make_prediction)
    graph.add_edge("analyze", "predict")
    graph.add_edge("predict", END)
    return graph.compile()
```

---

## API Routes Pattern

```typescript
// frontend/src/app/api/predictions/route.ts
import { auth } from '@clerk/nextjs/server';
import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  const { userId } = await auth();
  if (!userId) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();
    // Call ML backend
    const response = await fetch(`${process.env.ML_BACKEND_URL}/api/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: 'Internal error' }, { status: 500 });
  }
}
```

---

## Database Schema

```sql
-- Predictions table
CREATE TABLE predictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  prediction_type TEXT NOT NULL,
  value JSONB NOT NULL,
  confidence FLOAT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Agent runs table
CREATE TABLE agent_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  agent_type TEXT NOT NULL,
  input JSONB NOT NULL,
  output JSONB,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);

-- Strategies table
CREATE TABLE strategies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  code TEXT NOT NULL,
  backtest_results JSONB,
  is_active BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Enable RLS
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY "Users can view own predictions" ON predictions
  FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY "Users can insert own predictions" ON predictions
  FOR INSERT WITH CHECK (auth.uid()::text = user_id);
```

---

## Environment Variables

### Frontend (.env.local)
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=
XAI_API_KEY=
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=trade-nexus
ML_BACKEND_URL=http://localhost:8000
```

### Backend (.env)
```
XAI_API_KEY=
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=trade-nexus-backend
SUPABASE_URL=
SUPABASE_KEY=
```

---

## Agent Descriptions

### TypeScript Agents (Frontend)

| Agent | Purpose | Triggers |
|-------|---------|----------|
| **Strategy Agent** | Generates trading strategies based on market conditions | User request, ML signals |
| **Decision Agent** | Makes buy/sell/hold decisions | Strategy signals, portfolio state |
| **Orchestrator** | Coordinates multi-agent workflows | Scheduled, event-driven |

### Python Agents (Backend)

| Agent | Purpose | Input |
|-------|---------|-------|
| **Predictor** | LSTM/Prophet price forecasts | Historical prices, features |
| **Anomaly** | Detects market anomalies | Real-time price/volume |
| **Optimizer** | Portfolio allocation | Current holdings, predictions |

---

## Common Tasks

### Adding a New ML Model

1. Create model in `backend/src/models/`
2. Add training logic in `backend/src/services/training.py`
3. Expose via endpoint in `backend/src/api/routes.py`
4. Add schema in `backend/src/schemas/`

### Adding a New Agent

**TypeScript:**
1. Create agent in `frontend/src/lib/ai/`
2. Use AI SDK v5 `generateText` or `streamText`
3. Add to orchestrator routing

**Python:**
1. Create agent in `backend/src/agents/`
2. Define state and nodes for LangGraph
3. Add to graph orchestration

### Adding a New Dashboard Page

1. Create route in `frontend/src/app/(dashboard)/`
2. Add TanStack Query hook in `frontend/src/hooks/`
3. Create components in `frontend/src/components/`

---

## Testing Checklist

- [ ] TypeScript compiles without errors
- [ ] ESLint passes
- [ ] API routes return correct status codes
- [ ] Auth middleware protects routes
- [ ] ML endpoints return valid predictions
- [ ] Agent workflows complete successfully

---

## Debugging

### LangSmith
- Frontend traces: Check `LANGSMITH_PROJECT=trade-nexus`
- Backend traces: Check `LANGSMITH_PROJECT=trade-nexus-backend`
- View at: https://smith.langchain.com

### Supabase
- Check logs in Supabase dashboard
- Verify RLS policies for data access issues

### Vercel/Backend Logs
- Frontend: Vercel dashboard logs
- Backend: `uv run uvicorn` console output

---

## Code Style

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Components | PascalCase | `AgentCard.tsx` |
| Hooks | camelCase with `use` | `use-agents.ts` |
| Stores | kebab-case with `-store` | `settings-store.ts` |
| Utils | camelCase | `formatPrice.ts` |
| Python modules | snake_case | `predictor_agent.py` |

### Import Order

```typescript
// 1. External libraries
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';

// 2. Internal components
import { Button } from '@/components/ui/button';
import { AgentCard } from '@/components/agents/agent-card';

// 3. Hooks and stores
import { useAgents } from '@/hooks/use-agents';
import { useSettingsStore } from '@/stores/settings-store';

// 4. Lib and utils
import { supabase } from '@/lib/supabase/client';
import { cn } from '@/lib/utils';

// 5. Types
import type { Agent } from '@/types/agents';
```

---

## Resources

- [Next.js 16 Docs](https://nextjs.org/docs)
- [AI SDK v5 Docs](https://sdk.vercel.ai/docs)
- [TanStack Query Docs](https://tanstack.com/query/latest)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [shadcn/ui](https://ui.shadcn.com)
- [Clerk Docs](https://clerk.com/docs)
- [Supabase Docs](https://supabase.com/docs)
