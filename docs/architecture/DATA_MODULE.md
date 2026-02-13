# Data Module Architecture

## Overview

The Data Module handles all market data operations:
- Multi-exchange connectivity
- Multiple asset classes (crypto, stocks, forex)
- Data transformations (ticks → OHLCV)
- Filtering and queries
- Large-scale storage

## Challenges

1. **Multi-Exchange**: Different APIs, rate limits, data formats
2. **Data Volume**: Tick data = millions of rows per day per symbol
3. **Transformations**: Custom candle generation, filtering
4. **Storage**: Time-series optimized, cost-effective
5. **Real-time + Historical**: Both use cases

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA MODULE                                             │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                         DATA API (GraphQL / REST)                            │   │
│   │                                                                              │   │
│   │   Queries:                                                                   │   │
│   │   • getCandles(symbol, interval, start, end)                                │   │
│   │   • getTicks(symbol, start, end, filters?)                                  │   │
│   │   • getOrderBook(symbol, depth)                                             │   │
│   │   • aggregate(symbol, customLogic)                                          │   │
│   │   • filter(query)                                                           │   │
│   │                                                                              │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                           │
│                    ┌─────────────────────┴─────────────────────┐                    │
│                    │                                           │                    │
│                    ▼                                           ▼                    │
│   ┌──────────────────────────────┐       ┌──────────────────────────────┐          │
│   │     TRANSFORMATION ENGINE    │       │      FILTER ENGINE           │          │
│   │                              │       │                              │          │
│   │ • Ticks → OHLCV             │       │ • Time ranges                │          │
│   │ • Custom intervals          │       │ • Spread thresholds          │          │
│   │ • Volume profiles           │       │ • Volume conditions          │          │
│   │ • VWAP, TWAP               │       │ • Volatility filters         │          │
│   │ • Indicator calculation     │       │ • Custom predicates          │          │
│   └──────────────────────────────┘       └──────────────────────────────┘          │
│                    │                                           │                    │
│                    └─────────────────────┬─────────────────────┘                    │
│                                          │                                           │
│                                          ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                         TIME-SERIES STORAGE                                  │   │
│   │                                                                              │   │
│   │   Hot Data (last 30 days):        Cold Data (historical):                   │   │
│   │   • Supabase / Redis               • Azure Blob Storage                     │   │
│   │   • Fast queries                   • Cheap storage                          │   │
│   │   • Real-time inserts              • Batch queries (Parquet/JSON)           │   │
│   │                                                                              │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                           │
│                                          ▼                                           │
│   ┌─────────────────────────────────────────────────────────────────────────────┐   │
│   │                         EXCHANGE CONNECTORS                                  │   │
│   │                                                                              │   │
│   │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐          │   │
│   │   │ Binance │  │Coinbase │  │ Kraken  │  │ Alpaca  │  │  IBKR   │          │   │
│   │   │ (Crypto)│  │ (Crypto)│  │ (Crypto)│  │ (Stocks)│  │ (Stocks)│          │   │
│   │   └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘          │   │
│   │                                                                              │   │
│   │   Unified Interface:                                                         │   │
│   │   • subscribe(symbol) → WebSocket stream                                    │   │
│   │   • fetchHistorical(symbol, interval, range) → OHLCV[]                     │   │
│   │   • fetchTicks(symbol, range) → Tick[]                                     │   │
│   │   • fetchOrderBook(symbol) → OrderBook                                     │   │
│   │                                                                              │   │
│   └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Types

### Tick Data

```typescript
interface Tick {
  timestamp: number;      // Unix ms
  symbol: string;         // e.g., "BTCUSDT"
  exchange: string;       // e.g., "binance"
  price: number;
  quantity: number;
  side: 'buy' | 'sell';
  tradeId: string;
}
```

### Order Book (BBDO - Best Bid/Best Offer)

```typescript
interface OrderBookSnapshot {
  timestamp: number;
  symbol: string;
  exchange: string;
  bids: [price: number, quantity: number][]; // Sorted desc
  asks: [price: number, quantity: number][]; // Sorted asc
  spread: number;
  spreadPercent: number;
}
```

### OHLCV Candle

```typescript
interface Candle {
  timestamp: number;
  symbol: string;
  exchange: string;
  interval: string;       // '1m', '5m', '1h', '4h', '1d'
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  trades: number;
  vwap?: number;          // Volume-weighted average price
}
```

## Filter Engine

### Filter Types

```typescript
interface DataFilter {
  // Time filters
  timeRange?: {
    start: Date;
    end: Date;
  };
  
  // Market hours
  marketHours?: {
    only: 'premarket' | 'regular' | 'aftermarket' | 'all';
    timezone: string;
  };
  
  // Spread filter (for order book data)
  spread?: {
    max?: number;         // Max spread in price units
    maxPercent?: number;  // Max spread as percentage
  };
  
  // Volume filter
  volume?: {
    min?: number;
    max?: number;
    minRelative?: number; // e.g., 1.5 = 150% of average
  };
  
  // Volatility filter
  volatility?: {
    min?: number;         // Min ATR or std dev
    max?: number;
  };
  
  // Custom predicate (advanced)
  custom?: string;        // e.g., "close > sma(20) AND rsi(14) < 30"
}
```

### Example: Trader's Use Case

> "I want all days from the past year where the pre-market spread was less than 0.05% and volume was above average"

```typescript
const filteredData = await dataModule.filter({
  symbol: "BTCUSDT",
  timeRange: {
    start: new Date("2025-02-01"),
    end: new Date("2026-02-01")
  },
  marketHours: {
    only: "premarket",
    timezone: "America/New_York"
  },
  spread: {
    maxPercent: 0.05
  },
  volume: {
    minRelative: 1.0  // Above average
  }
});

// Returns: List of specific days/time ranges that match
// Then convert to candles for Lona backtesting:
const candles = await dataModule.toCandles(filteredData, "1h");
```

## Transformation Engine

### Ticks to OHLCV

```typescript
interface AggregationConfig {
  interval: string;           // '1m', '5m', '1h', '4h', '1d', 'custom'
  customMinutes?: number;     // For custom intervals
  
  // What to include
  includeVWAP: boolean;
  includeTradeCount: boolean;
  
  // Gap handling
  fillGaps: boolean;
  gapFillMethod: 'previous' | 'zero' | 'interpolate';
}

async function aggregateTicks(
  ticks: Tick[],
  config: AggregationConfig
): Promise<Candle[]> {
  // Group by interval
  // Calculate OHLCV for each group
  // Optionally fill gaps
  return candles;
}
```

### Custom Aggregations

```typescript
// Volume Profile
interface VolumeProfile {
  priceLevel: number;
  volume: number;
  buyVolume: number;
  sellVolume: number;
}

// VWAP
interface VWAPResult {
  vwap: number;
  upperBand: number;  // +1 std dev
  lowerBand: number;  // -1 std dev
}
```

## Storage Strategy

### Hot Storage (TimescaleDB)

For recent data (last 30-90 days):

```sql
-- TimescaleDB hypertable for ticks
CREATE TABLE ticks (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    side CHAR(1) NOT NULL, -- 'B' or 'S'
    trade_id VARCHAR(50)
);

SELECT create_hypertable('ticks', 'time');

-- Compression policy (older than 7 days)
ALTER TABLE ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, exchange'
);

SELECT add_compression_policy('ticks', INTERVAL '7 days');

-- Retention policy (move to cold after 90 days)
SELECT add_retention_policy('ticks', INTERVAL '90 days');
```

### Cold Storage (Azure Blob Storage)

For historical data:

```
tradenexusdata.blob.core.windows.net/
├── ohlcv/                      # Lona-compatible OHLCV
│   ├── binance/
│   │   ├── BTCUSDT/
│   │   │   ├── 1h/
│   │   │   │   └── 2024-01.json
│   │   │   └── 1d/
│   │   │       └── 2024.json
├── ticks/                      # Extended data (if needed)
│   ├── binance/
│   │   ├── BTCUSDT/
│   │   │   └── 2024-01-01.parquet
├── exports/                    # Ready for Lona upload
│   └── btc-1h-2024.json
```

### Lona-Compatible Format

**IMPORTANT**: All OHLCV data must match Lona's expected format:

```typescript
// Base format (required by Lona)
interface LonaOHLCV {
  timestamp: number;  // Unix timestamp in milliseconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

// JSON file format
{
  "symbol": "BTCUSDT",
  "interval": "1h",
  "exchange": "binance",
  "data": [
    { "timestamp": 1707350400000, "open": 42150.5, "high": 42300.0, "low": 42100.0, "close": 42250.0, "volume": 1234.56 },
    { "timestamp": 1707354000000, "open": 42250.0, "high": 42400.0, "low": 42200.0, "close": 42350.0, "volume": 1456.78 }
  ]
}
```

**Export function for Lona**:
```typescript
async function exportForLona(
  symbol: string, 
  interval: string, 
  startDate: Date, 
  endDate: Date
): Promise<LonaOHLCV[]> {
  const data = await getCandles(symbol, interval, startDate, endDate);
  
  // Strip to Lona-compatible fields only
  return data.map(({ timestamp, open, high, low, close, volume }) => ({
    timestamp,
    open,
    high,
    low,
    close,
    volume,
  }));
}
```

Query with **DuckDB** for analytical queries on Parquet files.

### Storage Estimates

| Data Type | Per Symbol/Day | Per Year | Notes |
|-----------|---------------|----------|-------|
| Ticks (BTC) | ~500MB | ~180GB | Compressed Parquet |
| Candles 1m | ~2MB | ~700MB | |
| Candles 1h | ~50KB | ~18MB | |
| Order Book | ~1GB | ~365GB | Snapshots every 1s |

## Exchange Connectors

### Unified Interface

```typescript
interface ExchangeConnector {
  name: string;
  type: 'crypto' | 'stocks' | 'forex';
  
  // Connection
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  
  // Real-time
  subscribeTicks(symbol: string, callback: (tick: Tick) => void): void;
  subscribeOrderBook(symbol: string, callback: (ob: OrderBook) => void): void;
  
  // Historical
  fetchCandles(symbol: string, interval: string, start: Date, end: Date): Promise<Candle[]>;
  fetchTicks(symbol: string, start: Date, end: Date): Promise<Tick[]>;
  
  // Metadata
  getSymbols(): Promise<SymbolInfo[]>;
  getExchangeInfo(): ExchangeInfo;
}
```

### Supported Exchanges (Proposed)

| Exchange | Asset Class | API Type | Rate Limits | Notes |
|----------|-------------|----------|-------------|-------|
| Binance | Crypto | REST + WS | 1200/min | Primary crypto |
| Coinbase | Crypto | REST + WS | 10/sec | US crypto |
| Kraken | Crypto | REST + WS | 15/sec | EU crypto |
| Alpaca | US Stocks | REST + WS | 200/min | Commission-free |
| IBKR | Global | FIX + TWS | Complex | Most comprehensive |
| Polygon.io | US Stocks | REST + WS | Varies | Good historical |

## API Design

### REST Endpoints

```
GET  /api/data/candles?symbol=BTCUSDT&interval=1h&start=2024-01-01&end=2024-12-31
GET  /api/data/ticks?symbol=BTCUSDT&start=2024-01-01T00:00:00Z&end=2024-01-01T01:00:00Z
GET  /api/data/orderbook?symbol=BTCUSDT&depth=20
POST /api/data/filter   (body: FilterQuery)
POST /api/data/aggregate (body: AggregationConfig)
GET  /api/data/symbols?exchange=binance&type=crypto
```

### WebSocket

```typescript
// Subscribe to real-time ticks
ws.send(JSON.stringify({
  action: 'subscribe',
  channel: 'ticks',
  symbol: 'BTCUSDT'
}));

// Receive
{
  "channel": "ticks",
  "data": {
    "timestamp": 1707836400000,
    "symbol": "BTCUSDT",
    "price": 97250.50,
    "quantity": 0.15,
    "side": "buy"
  }
}
```

## Technology Recommendations

| Component | Recommendation | Alternative |
|-----------|---------------|-------------|
| Hot Storage | TimescaleDB | QuestDB |
| Cold Storage | S3 + Parquet | ClickHouse |
| Query Engine | DuckDB | AWS Athena |
| API | FastAPI | Rust (for perf) |
| Real-time | WebSocket | gRPC streams |
| Message Queue | Redis Streams | Kafka |

## Implementation Priority

1. **Phase 1**: Binance connector + basic candle storage (extend current)
2. **Phase 2**: Tick data storage + TimescaleDB
3. **Phase 3**: Filter engine + transformations
4. **Phase 4**: Additional exchanges
5. **Phase 5**: Order book data + cold storage

## Open Questions

1. **Self-hosted vs Managed**: TimescaleDB Cloud vs self-hosted?
2. **Stock Data Provider**: Alpaca, Polygon, or IBKR?
3. **Cold Storage**: S3 or cheaper alternative?
4. **Budget**: What's acceptable monthly cost for data storage?
