import { getLiveEngineConfig } from './config';

export class LiveEngineError extends Error {
  statusCode: number | null;

  constructor(message: string, statusCode: number | null = null) {
    super(message);
    this.name = 'LiveEngineError';
    this.statusCode = statusCode;
  }
}

// Response types matching actual live-engine API contracts
interface PortfolioRow {
  id: string;
  name: string;
  balance: number;
  initial_balance: number;
  mode: string;
  broker: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}

interface PositionData {
  asset: string;
  amount: number;
  avgPrice: number;
  currentPrice: number;
  unrealizedPnl: number;
}

interface TradeRow {
  id: string;
  portfolio_id: string;
  asset: string;
  side: string;
  type: string;
  amount: number;
  price: number;
  status: string;
  created_at: string;
}

interface StrategyRow {
  id: string;
  name: string;
  description: string;
  status: string;
  python_code: string;
  typescript_code: string;
  explanation: string;
  dependencies: string[];
  conversion_notes: string;
  asset: string;
  interval: string;
  parameters: Record<string, unknown>;
  portfolio_id: string | null;
  user_id: string;
  created_at: string;
  updated_at: string;
}

interface LogRow {
  id: string;
  strategy_id: string;
  level: string;
  message: string;
  created_at: string;
}

export class LiveEngineClient {
  private baseUrl: string;
  private serviceKey: string;

  constructor(config?: { url?: string; serviceKey?: string }) {
    const c = { ...getLiveEngineConfig(), ...config };
    this.baseUrl = c.url;
    this.serviceKey = c.serviceKey;
  }

  private headers(): Record<string, string> {
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${this.serviceKey}`,
    };
  }

  private async request<T>(
    method: string,
    path: string,
    options: { body?: unknown; params?: Record<string, string> } = {},
  ): Promise<T> {
    const url = new URL(path, this.baseUrl);
    if (options.params) {
      for (const [key, value] of Object.entries(options.params)) {
        url.searchParams.set(key, value);
      }
    }

    const response = await fetch(url.toString(), {
      method,
      headers: this.headers(),
      body: options.body ? JSON.stringify(options.body) : undefined,
    });

    if (!response.ok) {
      let detail: string;
      try {
        const body = await response.json();
        detail = body?.error ?? body?.message ?? response.statusText;
      } catch {
        detail = response.statusText;
      }
      throw new LiveEngineError(
        `live-engine API error ${response.status}: ${detail}`,
        response.status,
      );
    }

    return response.json() as Promise<T>;
  }

  // ── Paper trading ──────────────────────────────────────

  /** Create a paper trading portfolio. Server hardcodes name to "Paper Trading Portfolio". */
  async createPortfolio(_name: string, initialBalance = 10000) {
    const resp = await this.request<{ success: boolean; portfolio: PortfolioRow }>(
      'POST',
      '/api/paper',
      { body: { action: 'create_portfolio', initialBalance } },
    );
    return { portfolio: resp.portfolio };
  }

  /** Execute a paper trade. Server expects nested `trade` object with `asset`/`amount`. */
  async executeTrade(
    portfolioId: string,
    asset: string,
    side: 'buy' | 'sell',
    amount: number,
    type: 'market' | 'limit' = 'market',
    price?: number,
  ) {
    const resp = await this.request<{ success: boolean; trade: TradeRow; newBalance: number }>(
      'POST',
      '/api/paper',
      {
        body: {
          action: 'execute_trade',
          portfolioId,
          trade: { asset, side, type, amount, price },
        },
      },
    );
    return { trade: resp.trade, newBalance: resp.newBalance };
  }

  /** Get portfolio with positions and P&L. */
  async getPortfolio(portfolioId: string) {
    const resp = await this.request<{
      portfolio: PortfolioRow & { totalValue: number; pnl: number; pnlPercent: number };
      positions: PositionData[];
      trades: TradeRow[];
    }>('GET', '/api/paper', { params: { portfolioId } });
    return {
      portfolio: resp.portfolio,
      positions: resp.positions,
      totalValue: resp.portfolio.totalValue,
      pnl: resp.portfolio.pnl,
      pnlPercent: resp.portfolio.pnlPercent,
    };
  }

  /** List all paper portfolios. */
  async listPortfolios() {
    const resp = await this.request<{ portfolios: PortfolioRow[] }>('GET', '/api/paper');
    return resp.portfolios;
  }

  // ── Strategies ─────────────────────────────────────────

  /** Create a strategy on live-engine. */
  async createStrategy(data: {
    name: string;
    python_code: string;
    typescript_code: string;
    description?: string;
    explanation?: string;
    dependencies?: string[];
    conversion_notes?: string;
    asset?: string;
    interval?: string;
    parameters?: Record<string, unknown>;
    portfolio_id?: string;
  }) {
    const resp = await this.request<{ strategy: StrategyRow }>('POST', '/api/strategies', { body: data });
    return resp.strategy;
  }

  /** Update strategy fields (e.g. status). */
  async updateStrategy(id: string, data: Record<string, unknown>) {
    const resp = await this.request<{ strategy: StrategyRow }>('PATCH', '/api/strategies', { body: { id, ...data } });
    return resp.strategy;
  }

  /** List all strategies. */
  async listStrategies() {
    const resp = await this.request<{ strategies: StrategyRow[] }>('GET', '/api/strategies');
    return resp.strategies;
  }

  /** Get single strategy with recent logs. */
  async getStrategy(id: string) {
    const resp = await this.request<{ strategy: StrategyRow; logs: LogRow[] }>(
      'GET',
      '/api/strategies',
      { params: { id } },
    );
    return { ...resp.strategy, logs: resp.logs };
  }

  /** Get paginated strategy logs. */
  async getStrategyLogs(id: string, limit = 50, offset = 0) {
    return this.request<{ logs: LogRow[]; total: number }>(
      'GET',
      `/api/strategies/${id}/logs`,
      { params: { limit: String(limit), offset: String(offset) } },
    );
  }

  // ── Code conversion ────────────────────────────────────

  async convertCode(
    pythonCode: string,
    options?: { context?: string; validate?: boolean; explain?: boolean },
  ) {
    return this.request<{
      success: boolean;
      conversion: {
        typescript: string;
        dependencies: string[];
        notes: string;
        intent: string;
      };
      validation?: { isValid: boolean; issues: string[]; suggestions: string[] };
      explanation?: string;
    }>('POST', '/api/convert', {
      body: {
        pythonCode,
        context: options?.context,
        validate: options?.validate ?? true,
        explain: options?.explain ?? false,
      },
    });
  }

  // ── Health check ───────────────────────────────────────

  async ping(): Promise<boolean> {
    try {
      const response = await fetch(this.baseUrl, {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}

let _client: LiveEngineClient | null = null;

export function getLiveEngineClient(): LiveEngineClient {
  if (!_client) {
    _client = new LiveEngineClient();
  }
  return _client;
}
