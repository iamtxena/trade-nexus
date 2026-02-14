# Knowledge Base Architecture

## Overview

The Knowledge Base provides hybrid storage (SQL + Vector) for:
- Trading patterns and strategies
- Market regime history
- News and sentiment (continuous feed)
- Lessons learned from trades

## Gate3 Canonical Schema (v1.0)

The Gate3 canonical schema is frozen at version `1.0` and implemented by:

- migration: `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/supabase/migrations/002_kb_schema.sql`
- runtime models: `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/backend/src/platform_api/knowledge/models.py`

Canonical entities:

1. `KnowledgePattern` (patterns library)
2. `MarketRegime` (active and historical regimes)
3. `LessonLearned` (feedback from backtests/deployments)
4. `MacroEvent` (macro/news events with impact metadata)
5. `CorrelationEdge` (asset correlation graph edges)

Governance requirements:

1. Every record includes `schema_version`.
2. Additive evolution is allowed in-place; breaking changes require new schema version and migration notes.
3. KB ingestion is idempotent and keyed by event fingerprint.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              KNOWLEDGE BASE                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                         QUERY INTERFACE                                      │   │
│   │                                                                              │   │
│   │   query("momentum strategies for sideways BTC")                             │   │
│   │         │                                                                    │   │
│   │         ├──▶ SQL: WHERE type='momentum' AND asset='BTC'                     │   │
│   │         │                                                                    │   │
│   │         └──▶ Vector: semantic_search("sideways market momentum")            │   │
│   │                                                                              │   │
│   │   Result: Merged, ranked, deduplicated                                      │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                           │
│                    ┌─────────────────────┴─────────────────────┐                    │
│                    │                                           │                    │
│                    ▼                                           ▼                    │
│   ┌──────────────────────────────┐       ┌──────────────────────────────┐          │
│   │     POSTGRESQL (SQL)          │       │     VECTOR DB                │          │
│   │                               │       │     (pgvector / Pinecone)    │          │
│   │ Tables:                       │       │                              │          │
│   │ • strategy_patterns           │       │ Collections:                 │          │
│   │ • market_regimes              │       │ • strategies (embeddings)    │          │
│   │ • trade_history               │       │ • news_articles              │          │
│   │ • news_events                 │       │ • market_commentary          │          │
│   │ • lessons_learned             │       │ • lessons                    │          │
│   └──────────────────────────────┘       └──────────────────────────────┘          │
│                                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                         NEWS FEED INGESTION                                  │   │
│   │                                                                              │   │
│   │   Sources:                    Regions:           Sectors:                   │   │
│   │   • RSS feeds                 • Europe           • Crypto                   │   │
│   │   • Twitter/X                 • Spain            • Tech stocks              │   │
│   │   • News APIs                 • United States    • Forex                    │   │
│   │   • Reddit                    • Asia             • Commodities              │   │
│   │                                                                              │   │
│   │   Pipeline: Fetch → Parse → Embed → Store → Index                          │   │
│   │   Frequency: Every 5-15 minutes                                             │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Database Schema

### PostgreSQL Tables

```sql
-- Strategy patterns library
CREATE TABLE strategy_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- momentum, mean_reversion, breakout, etc.
    description TEXT,
    conditions JSONB, -- Entry/exit rules
    suitable_regimes TEXT[], -- bull, bear, sideways, high_vol, low_vol
    assets TEXT[], -- BTC, ETH, stocks, forex
    timeframes TEXT[], -- 1m, 5m, 1h, 4h, 1d
    historical_performance JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Market regime history
CREATE TABLE market_regimes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset VARCHAR(50) NOT NULL,
    regime VARCHAR(50) NOT NULL, -- bull, bear, sideways
    volatility VARCHAR(20), -- low, medium, high
    start_date DATE NOT NULL,
    end_date DATE,
    indicators JSONB, -- RSI, VIX, etc. at the time
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Trade history (for learning)
CREATE TABLE trade_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id UUID REFERENCES strategy_patterns(id),
    asset VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL, -- buy, sell
    entry_price DECIMAL(20, 8),
    exit_price DECIMAL(20, 8),
    quantity DECIMAL(20, 8),
    pnl DECIMAL(20, 8),
    pnl_percent DECIMAL(10, 4),
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    market_regime VARCHAR(50),
    notes TEXT,
    lessons TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

-- News events
CREATE TABLE news_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    summary TEXT,
    source VARCHAR(100),
    url TEXT,
    region VARCHAR(50), -- europe, spain, us, asia
    sector VARCHAR(50), -- crypto, stocks, forex, commodities
    sentiment DECIMAL(3, 2), -- -1 to 1
    impact VARCHAR(20), -- low, medium, high
    assets_mentioned TEXT[],
    published_at TIMESTAMP,
    fetched_at TIMESTAMP DEFAULT NOW()
);

-- Lessons learned
CREATE TABLE lessons_learned (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_id UUID REFERENCES trade_history(id),
    lesson TEXT NOT NULL,
    category VARCHAR(50), -- entry, exit, sizing, timing, etc.
    applicable_to TEXT[], -- asset types, market conditions
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_patterns_type ON strategy_patterns(type);
CREATE INDEX idx_patterns_assets ON strategy_patterns USING GIN(assets);
CREATE INDEX idx_regimes_asset_date ON market_regimes(asset, start_date);
CREATE INDEX idx_news_region_sector ON news_events(region, sector);
CREATE INDEX idx_news_published ON news_events(published_at DESC);
```

### Vector Collections

Using **pgvector** (PostgreSQL extension) or **Pinecone**:

```sql
-- Add vector extension to PostgreSQL
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding columns
ALTER TABLE strategy_patterns 
ADD COLUMN embedding vector(1536); -- OpenAI ada-002 dimension

ALTER TABLE news_events
ADD COLUMN embedding vector(1536);

ALTER TABLE lessons_learned
ADD COLUMN embedding vector(1536);

-- Create indexes for similarity search
CREATE INDEX idx_patterns_embedding ON strategy_patterns 
USING ivfflat (embedding vector_cosine_ops);

CREATE INDEX idx_news_embedding ON news_events 
USING ivfflat (embedding vector_cosine_ops);
```

## Query Interface

### API Endpoints

```typescript
// Knowledge Base API
interface KnowledgeBaseAPI {
  // Hybrid search (SQL + Vector)
  search(query: string, filters?: Filters): SearchResult[];
  
  // Get strategy patterns
  getPatterns(type?: string, asset?: string): StrategyPattern[];
  
  // Get current market regime
  getCurrentRegime(asset: string): MarketRegime;
  
  // Get recent news
  getNews(region?: string, sector?: string, since?: Date): NewsEvent[];
  
  // Get lessons for similar situations
  getLessons(context: TradingContext): Lesson[];
  
  // Store new pattern
  addPattern(pattern: StrategyPattern): void;
  
  // Record trade for learning
  recordTrade(trade: Trade, lesson?: string): void;
}
```

### Example Queries

```typescript
// "Find momentum strategies that worked in sideways BTC markets"
const results = await kb.search(
  "momentum strategies sideways market",
  {
    type: "momentum",
    assets: ["BTC"],
    regimes: ["sideways"]
  }
);

// "What news is affecting crypto today?"
const news = await kb.getNews({
  sector: "crypto",
  since: new Date(Date.now() - 24 * 60 * 60 * 1000), // Last 24h
  minImpact: "medium"
});

// "What lessons did we learn from similar market conditions?"
const lessons = await kb.getLessons({
  asset: "BTC",
  regime: "sideways",
  volatility: "low"
});
```

## News Feed Ingestion

### Sources

| Source | Type | Regions | Update Frequency |
|--------|------|---------|------------------|
| CoinDesk RSS | Crypto news | Global | 5 min |
| Bloomberg RSS | Markets | US, Europe | 15 min |
| Reuters RSS | Markets | Global | 15 min |
| Twitter/X API | Social sentiment | Global | 5 min |
| Reddit API | r/cryptocurrency, r/stocks | Global | 15 min |
| El Economista RSS | Spain markets | Spain | 30 min |
| Financial Times RSS | Europe markets | Europe | 15 min |

### Ingestion Pipeline

```typescript
// News ingestion worker (runs on cron)
async function ingestNews() {
  const sources = getConfiguredSources();
  
  for (const source of sources) {
    // 1. Fetch new articles
    const articles = await fetchFromSource(source);
    
    // 2. Parse and extract
    const parsed = articles.map(parseArticle);
    
    // 3. Detect assets mentioned
    const withAssets = parsed.map(detectAssets);
    
    // 4. Analyze sentiment
    const withSentiment = await analyzeSentiment(withAssets);
    
    // 5. Generate embeddings
    const withEmbeddings = await generateEmbeddings(withSentiment);
    
    // 6. Store in database
    await storeNews(withEmbeddings);
    
    // 7. Alert if high-impact
    const highImpact = withSentiment.filter(n => n.impact === 'high');
    if (highImpact.length > 0) {
      await alertTradingAgent(highImpact);
    }
  }
}
```

## Technology Options

### Option A: PostgreSQL + pgvector (Recommended)

**Pros**:
- Single database for SQL + Vector
- Supabase supports pgvector
- Simpler infrastructure
- Transaction support

**Cons**:
- Vector performance at scale

### Option B: PostgreSQL + Pinecone

**Pros**:
- Better vector performance at scale
- Managed service

**Cons**:
- Two databases to maintain
- Additional cost
- Sync complexity

### Recommendation

Start with **PostgreSQL + pgvector** (can use existing Supabase). Migrate to Pinecone only if vector search becomes a bottleneck.

## Implementation Priority

1. **Phase 1**: Basic SQL tables + patterns library
2. **Phase 2**: Add vector search with pgvector
3. **Phase 3**: News ingestion pipeline
4. **Phase 4**: Learning from trades
