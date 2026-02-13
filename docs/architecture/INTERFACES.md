# Interface Definitions

> 🔗 **Critical for parallel development** - Define these first, then teams can work independently

## Overview

These interfaces are the contracts between modules. Once defined, each module can be developed in parallel by different people.

## Module Dependencies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DEPENDENCY GRAPH                                        │
│                                                                              │
│                    ┌────────────────────────┐                               │
│                    │    PLATFORM API        │                               │
│                    │   (trade-nexus-api)    │                               │
│                    └───────────┬────────────┘                               │
│                                │                                             │
│           ┌────────────────────┼────────────────────┐                       │
│           │                    │                    │                       │
│           ▼                    ▼                    ▼                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  DATA MODULE    │  │ KNOWLEDGE BASE  │  │  LONA GATEWAY   │             │
│  │ (trader-data)   │  │   (Supabase)    │  │    (existing)   │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│           │                    │                    │                       │
│           │                    │                    │                       │
│           ▼                    ▼                    ▼                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │  DATA SOURCES   │  │    VECTORS      │  │  LIVE ENGINE    │             │
│  │ Alpaca/Binance  │  │   (pgvector)    │  │   (existing)    │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

INDEPENDENT MODULES (no cross-dependencies):
• Data Module ← only depends on external data sources
• Knowledge Base ← only depends on Supabase  
• Live Engine fix ← isolated bug in separate repo

DEPENDENT MODULES (need interfaces first):
• Platform API ← needs Data Module + Knowledge Base + Lona interfaces
• CLI ← needs Platform API interface
• Agent Orchestrator ← needs all interfaces
```

---

## 1. Data Module Interface

**Repo**: `trader-data` (to be created)
**Owner**: TBD

### REST API

```typescript
// Base URL: https://data.trade-nexus.io/api/v1

// === OHLCV Data ===
GET /candles
  Query: symbol, interval, start?, end?, limit?
  Returns: Candle[]

GET /candles/bulk
  Body: { requests: CandleRequest[] }
  Returns: { [symbol]: Candle[] }

// === Real-time Quotes ===
GET /quote/:symbol
  Returns: Quote

// === News & Events ===
GET /news
  Query: symbols[]?, regions[]?, sectors[]?, since?, limit?
  Returns: NewsItem[]

GET /news/for-period
  Query: symbol, start, end
  Returns: NewsItem[]  // News that was available during this period

// === Custom Data (for backtesting with context) ===
GET /context/:symbol
  Query: start, end, interval, include[]  // include: news, sentiment, regime
  Returns: ContextualData[]

POST /data/upload
  Body: { name, symbol, interval, data: OHLCV[], metadata? }
  Returns: { dataId }

// === Filters ===
POST /filter
  Body: FilterQuery
  Returns: FilteredData

// === Symbols ===
GET /symbols
  Query: exchange?, assetClass?
  Returns: SymbolInfo[]
```

### TypeScript Types

```typescript
// types/data.ts

export interface Candle {
  timestamp: number;      // Unix ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  trades?: number;
  vwap?: number;
}

export interface Quote {
  symbol: string;
  bid: number;
  ask: number;
  last: number;
  volume: number;
  timestamp: number;
}

export interface NewsItem {
  id: string;
  title: string;
  summary: string;
  source: string;
  url: string;
  publishedAt: number;      // Unix ms
  symbols: string[];        // Mentioned assets
  sentiment: number;        // -1 to 1
  impact: 'low' | 'medium' | 'high';
  region: string;
  sector: string;
}

// For backtesting with news context
export interface ContextualCandle extends Candle {
  news: NewsItem[];         // News available at this candle's time
  sentiment: number;        // Aggregate sentiment
  regime?: 'bull' | 'bear' | 'sideways';
  volatility?: 'low' | 'medium' | 'high';
}

export interface FilterQuery {
  symbol: string;
  timeRange: { start: Date; end: Date };
  spread?: { maxPercent: number };
  volume?: { minRelative: number };
  volatility?: { min?: number; max?: number };
  news?: { minImpact: 'low' | 'medium' | 'high' };
  custom?: string;  // Custom predicate
}
```

### SDK

```typescript
// @trade-nexus/data-sdk

class DataClient {
  constructor(config: { apiUrl: string; apiKey: string });
  
  // OHLCV
  getCandles(symbol: string, interval: string, options?: CandleOptions): Promise<Candle[]>;
  getBulkCandles(requests: CandleRequest[]): Promise<Map<string, Candle[]>>;
  
  // Quotes
  getQuote(symbol: string): Promise<Quote>;
  
  // News
  getNews(options: NewsOptions): Promise<NewsItem[]>;
  getNewsForPeriod(symbol: string, start: Date, end: Date): Promise<NewsItem[]>;
  
  // Contextual (for backtesting with news)
  getContextualData(symbol: string, interval: string, start: Date, end: Date): Promise<ContextualCandle[]>;
  
  // Upload
  uploadData(name: string, symbol: string, interval: string, data: Candle[]): Promise<{ dataId: string }>;
  
  // Filter
  filter(query: FilterQuery): Promise<FilteredData>;
  
  // Symbols
  getSymbols(options?: SymbolOptions): Promise<SymbolInfo[]>;
}
```

---

## 2. Knowledge Base Interface

**Backend**: Supabase (existing)
**Owner**: TBD

### REST API

```typescript
// Via Supabase Edge Functions or direct Supabase client

// === Strategy Patterns ===
GET /patterns
  Query: type?, assets[]?, regimes[]?
  Returns: StrategyPattern[]

POST /patterns
  Body: StrategyPattern
  Returns: { id }

// === News (stored for historical context) ===
GET /news/historical
  Query: symbol, start, end
  Returns: NewsItem[]

POST /news/ingest
  Body: NewsItem[]
  Returns: { count }

// === Lessons ===
GET /lessons
  Query: category?, assets[]?
  Returns: Lesson[]

POST /lessons
  Body: Lesson
  Returns: { id }

// === Semantic Search ===
POST /search
  Body: { query: string, filters?: object, limit?: number }
  Returns: SearchResult[]  // Hybrid SQL + vector

// === Market Regimes ===
GET /regimes/:symbol
  Query: start?, end?
  Returns: MarketRegime[]

POST /regimes
  Body: MarketRegime
  Returns: { id }
```

### TypeScript Types

```typescript
// types/knowledge.ts

export interface StrategyPattern {
  id?: string;
  name: string;
  type: 'momentum' | 'mean_reversion' | 'breakout' | 'trend' | 'other';
  description: string;
  conditions: Record<string, any>;  // Entry/exit rules
  suitableRegimes: string[];
  assets: string[];
  timeframes: string[];
  performance?: {
    sharpe?: number;
    returns?: number;
    drawdown?: number;
  };
  embedding?: number[];  // For vector search
}

export interface Lesson {
  id?: string;
  tradeId?: string;
  lesson: string;
  category: 'entry' | 'exit' | 'sizing' | 'timing' | 'psychology' | 'other';
  applicableTo: string[];
  embedding?: number[];
}

export interface MarketRegime {
  id?: string;
  asset: string;
  regime: 'bull' | 'bear' | 'sideways';
  volatility: 'low' | 'medium' | 'high';
  startDate: string;
  endDate?: string;
  indicators: Record<string, number>;
}

export interface SearchResult {
  type: 'pattern' | 'news' | 'lesson';
  id: string;
  content: any;
  score: number;  // Relevance score
}
```

### SDK

```typescript
// @trade-nexus/knowledge-sdk

class KnowledgeClient {
  constructor(supabaseUrl: string, supabaseKey: string);
  
  // Patterns
  getPatterns(options?: PatternOptions): Promise<StrategyPattern[]>;
  savePattern(pattern: StrategyPattern): Promise<string>;
  
  // News (historical, for context)
  getHistoricalNews(symbol: string, start: Date, end: Date): Promise<NewsItem[]>;
  ingestNews(items: NewsItem[]): Promise<number>;
  
  // Lessons
  getLessons(options?: LessonOptions): Promise<Lesson[]>;
  saveLesson(lesson: Lesson): Promise<string>;
  
  // Semantic Search (hybrid)
  search(query: string, options?: SearchOptions): Promise<SearchResult[]>;
  
  // Regimes
  getCurrentRegime(symbol: string): Promise<MarketRegime | null>;
  getRegimeHistory(symbol: string, start?: Date, end?: Date): Promise<MarketRegime[]>;
  saveRegime(regime: MarketRegime): Promise<string>;
}
```

---

## 3. Lona Gateway Interface

**Backend**: lona.agency (existing)
**Owner**: Existing team

### REST API (Current)

```typescript
// Base URL: https://lona.agency/api

// === Strategies ===
POST /strategies/generate
  Body: { name, description, asset, timeframe }
  Returns: { strategyId, code }

GET /strategies
  Query: status?, sortBy?
  Returns: Strategy[]

GET /strategies/:id
  Returns: Strategy

// === Backtesting ===
POST /strategies/:id/backtest
  Body: { dataId, startDate?, endDate?, customData?: ContextualCandle[] }
  Returns: { backtestId }

GET /backtests/:id
  Returns: Backtest

GET /backtests/:id/report
  Returns: BacktestReport

// === Data ===
POST /data/upload
  Body: { name, symbol, interval, data: Candle[] }
  Returns: { dataId }

GET /data
  Returns: DataSet[]

// === Paper Trading ===
POST /deploy/paper
  Body: { strategyId, capital }
  Returns: { deploymentId }

GET /deployments/:id
  Returns: Deployment

POST /deployments/:id/stop
  Returns: { status }
```

### NEW: Custom Data Support (for news correlation)

```typescript
// PROPOSED ADDITION to Lona API

// Upload contextual data (OHLCV + news + sentiment)
POST /data/upload-contextual
  Body: {
    name: string;
    symbol: string;
    interval: string;
    data: ContextualCandle[];  // Includes news, sentiment per candle
  }
  Returns: { dataId }

// Backtest with news context available to strategy
POST /strategies/:id/backtest-contextual
  Body: {
    dataId: string;           // Contextual data ID
    enableNewsContext: true;  // Strategy can access .news on each candle
  }
  Returns: { backtestId }

// Strategy code can then access:
// candle.news[] - news items available at this candle's time
// candle.sentiment - aggregate sentiment score
// candle.regime - detected market regime
```

### TypeScript Types

```typescript
// types/lona.ts

export interface Strategy {
  id: string;
  name: string;
  description: string;
  code: string;
  asset: string;
  timeframe: string;
  status: 'draft' | 'tested' | 'deployed';
  score?: number;
  createdAt: string;
}

export interface Backtest {
  id: string;
  strategyId: string;
  dataId: string;
  status: 'running' | 'completed' | 'failed';
  startedAt: string;
  completedAt?: string;
}

export interface BacktestReport {
  backtestId: string;
  returns: number;
  sharpe: number;
  drawdown: number;
  winRate: number;
  trades: number;
  avgWin: number;
  avgLoss: number;
  profitFactor: number;
  tradeList: Trade[];
}

export interface Deployment {
  id: string;
  strategyId: string;
  mode: 'paper' | 'live';
  capital: number;
  status: 'running' | 'stopped' | 'error';
  pnl: number;
  trades: number;
  startedAt: string;
}
```

---

## 4. Platform API Interface

**Repo**: trade-nexus (main)
**Owner**: TBD

### REST API

```typescript
// Base URL: https://api.trade-nexus.io/v1

// === Authentication ===
POST /auth/login
POST /auth/register
GET /auth/me

// === Portfolio ===
GET /portfolio
  Returns: Portfolio

GET /portfolio/history
  Query: days?
  Returns: PortfolioHistory

GET /portfolio/positions
  Returns: Position[]

// === Trading ===
POST /trade
  Body: { symbol, side, quantity, type?, price? }
  Returns: Order

GET /orders
  Query: status?, limit?
  Returns: Order[]

GET /orders/:id
  Returns: Order

DELETE /orders/:id  // Cancel

// === Research ===
POST /research
  Body: { query: string, options?: { asset?, depth? } }
  Returns: ResearchResult

GET /research/sentiment/:symbol
  Returns: SentimentResult

// === Strategies ===
GET /strategies
  Query: status?
  Returns: Strategy[]

POST /strategies
  Body: { name, description }
  Returns: Strategy

POST /strategies/:id/backtest
  Body: { dataId, options?: BacktestOptions }
  Returns: Backtest

POST /strategies/:id/deploy
  Body: { mode: 'paper' | 'live', capital }
  Returns: Deployment

POST /strategies/:id/stop
  Returns: { status }

// === Data ===
GET /data/candles
  Query: symbol, interval, limit?
  Returns: Candle[]

GET /data/quote/:symbol
  Returns: Quote

GET /data/news
  Query: symbols[]?, since?
  Returns: NewsItem[]

// === Knowledge ===
GET /knowledge/patterns
  Query: type?, asset?
  Returns: StrategyPattern[]

POST /knowledge/search
  Body: { query, filters? }
  Returns: SearchResult[]

// === Alerts ===
GET /alerts
  Returns: Alert[]

POST /alerts
  Body: { type, symbol?, condition, action }
  Returns: Alert

DELETE /alerts/:id
```

### TypeScript Types

```typescript
// types/platform.ts

export interface Portfolio {
  totalValue: number;
  cash: number;
  pnlToday: number;
  pnlTodayPercent: number;
  pnlTotal: number;
  pnlTotalPercent: number;
  positions: Position[];
  activeStrategies: number;
}

export interface Position {
  symbol: string;
  quantity: number;
  avgCost: number;
  currentPrice: number;
  marketValue: number;
  pnl: number;
  pnlPercent: number;
}

export interface Order {
  id: string;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  type: 'market' | 'limit';
  price?: number;
  status: 'pending' | 'filled' | 'cancelled' | 'rejected';
  filledAt?: string;
  filledPrice?: number;
  createdAt: string;
}

export interface ResearchResult {
  summary: string;
  insights: string[];
  sentiment: number;
  sources: { title: string; url: string }[];
  suggestedStrategies?: Strategy[];
}

export interface Alert {
  id: string;
  type: 'price' | 'portfolio' | 'strategy';
  symbol?: string;
  condition: string;
  action: 'notify' | 'execute';
  active: boolean;
}
```

### SDK

```typescript
// @trade-nexus/sdk

class TradeNexusClient {
  constructor(config: { apiUrl: string; apiKey: string });
  
  // Auth
  login(email: string, password: string): Promise<Session>;
  getProfile(): Promise<User>;
  
  // Portfolio
  getPortfolio(): Promise<Portfolio>;
  getPortfolioHistory(days?: number): Promise<PortfolioHistory>;
  getPositions(): Promise<Position[]>;
  
  // Trading
  trade(params: TradeParams): Promise<Order>;
  getOrders(status?: string): Promise<Order[]>;
  getOrder(id: string): Promise<Order>;
  cancelOrder(id: string): Promise<void>;
  
  // Research
  research(query: string, options?: ResearchOptions): Promise<ResearchResult>;
  getSentiment(symbol: string): Promise<SentimentResult>;
  
  // Strategies
  getStrategies(status?: string): Promise<Strategy[]>;
  createStrategy(name: string, description: string): Promise<Strategy>;
  backtestStrategy(id: string, dataId: string, options?: BacktestOptions): Promise<Backtest>;
  deployStrategy(id: string, mode: 'paper' | 'live', capital: number): Promise<Deployment>;
  stopStrategy(id: string): Promise<void>;
  
  // Data (proxied from Data Module)
  getCandles(symbol: string, interval: string, limit?: number): Promise<Candle[]>;
  getQuote(symbol: string): Promise<Quote>;
  getNews(options?: NewsOptions): Promise<NewsItem[]>;
  
  // Knowledge (proxied from Knowledge Base)
  searchKnowledge(query: string, filters?: object): Promise<SearchResult[]>;
  getPatterns(options?: PatternOptions): Promise<StrategyPattern[]>;
  
  // Alerts
  getAlerts(): Promise<Alert[]>;
  createAlert(alert: AlertParams): Promise<Alert>;
  deleteAlert(id: string): Promise<void>;
}
```

---

## 5. CLI Interface

**Location**: `frontend/cli/` (existing)
**Owner**: TBD

### Commands (uses Platform API)

```bash
# Portfolio
trading-cli portfolio status
trading-cli portfolio history --days 30
trading-cli portfolio positions

# Trading
trading-cli trade buy BTC 0.1
trading-cli trade sell ETH 1.5 --limit 2500
trading-cli orders
trading-cli orders cancel <id>

# Research
trading-cli research "momentum strategies for BTC"
trading-cli research sentiment BTC

# Strategies
trading-cli strategy list
trading-cli strategy create "My Strategy" --description "..."
trading-cli strategy backtest <id> --data <dataId>
trading-cli strategy deploy <id> --mode paper --capital 10000
trading-cli strategy stop <id>

# Data
trading-cli data candles BTC 1h --limit 100
trading-cli data quote ETH
trading-cli data news --symbols BTC,ETH --since 24h

# Knowledge
trading-cli knowledge search "mean reversion crypto"
trading-cli knowledge patterns --type momentum

# Alerts
trading-cli alerts
trading-cli alerts create --type price --symbol BTC --condition ">50000"
trading-cli alerts delete <id>

# Config
trading-cli config set api-url https://api.trade-nexus.io
trading-cli config set api-key xxx
```

### Output Formats

```bash
# Default: human-readable
trading-cli portfolio status

# JSON (for scripts/agents)
trading-cli portfolio status --json

# Quiet (just values)
trading-cli portfolio status --quiet
```

---

## Interface Versioning

All interfaces use semantic versioning:

- **v1**: Initial release
- Breaking changes → increment major version
- New features → increment minor version

API URLs include version: `/api/v1/...`

SDK includes version in package: `@trade-nexus/sdk@1.0.0`

---

## Mock Implementations

For parallel development, each module should provide mocks:

```typescript
// @trade-nexus/data-sdk/mock
export const mockDataClient = {
  getCandles: async () => [
    { timestamp: Date.now(), open: 100, high: 105, low: 98, close: 102, volume: 1000 },
  ],
  getQuote: async () => ({ symbol: 'BTC', bid: 100, ask: 101, last: 100.5, volume: 5000, timestamp: Date.now() }),
  getNews: async () => [],
  // ...
};

// @trade-nexus/knowledge-sdk/mock
export const mockKnowledgeClient = {
  search: async () => [],
  getPatterns: async () => [],
  // ...
};
```

Teams can develop against mocks until real implementations are ready.
