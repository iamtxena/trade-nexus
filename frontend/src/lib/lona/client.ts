import type {
  LonaBacktestRequest,
  LonaBacktestResponse,
  LonaRegistrationResponse,
  LonaReport,
  LonaReportStatus,
  LonaStrategy,
  LonaStrategyFromDescriptionResponse,
  LonaSymbol,
} from './types';

const BINANCE_KLINES_URL = 'https://api.binance.com/api/v3/klines';
const BINANCE_MAX_LIMIT = 1000;

export class LonaClientError extends Error {
  statusCode: number | null;

  constructor(message: string, statusCode: number | null = null) {
    super(message);
    this.name = 'LonaClientError';
    this.statusCode = statusCode;
  }
}

function getConfig() {
  return {
    gatewayUrl: process.env.LONA_GATEWAY_URL ?? 'https://gateway.lona.agency',
    agentId: process.env.LONA_AGENT_ID ?? 'trade-nexus',
    agentName: process.env.LONA_AGENT_NAME ?? 'Trade Nexus Orchestrator',
    registrationSecret: process.env.LONA_AGENT_REGISTRATION_SECRET ?? '',
    token: process.env.LONA_AGENT_TOKEN ?? '',
    tokenTtlDays: Number(process.env.LONA_TOKEN_TTL_DAYS ?? '30'),
  };
}

export class LonaClient {
  private baseUrl: string;
  private agentId: string;
  private agentName: string;
  private registrationSecret: string;
  private token: string;
  private tokenTtlDays: number;

  constructor(config?: Partial<ReturnType<typeof getConfig>>) {
    const c = { ...getConfig(), ...config };
    this.baseUrl = c.gatewayUrl;
    this.agentId = c.agentId;
    this.agentName = c.agentName;
    this.registrationSecret = c.registrationSecret;
    this.token = c.token;
    this.tokenTtlDays = c.tokenTtlDays;
  }

  private authHeaders(): Record<string, string> {
    return {
      'X-API-Key': this.token,
      'X-User-Id': this.agentId,
      'Content-Type': 'application/json',
    };
  }

  private async request<T>(
    method: string,
    path: string,
    options: {
      body?: unknown;
      params?: Record<string, string | number | boolean>;
      timeout?: number;
      headers?: Record<string, string>;
    } = {},
  ): Promise<T> {
    const url = new URL(path, this.baseUrl);
    if (options.params) {
      for (const [key, value] of Object.entries(options.params)) {
        url.searchParams.set(key, String(value));
      }
    }

    const controller = new AbortController();
    const timeoutMs = options.timeout ?? 60_000;
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url.toString(), {
        method,
        headers: { ...this.authHeaders(), ...options.headers },
        body: options.body ? JSON.stringify(options.body) : undefined,
        signal: controller.signal,
      });

      await this.raiseForStatus(response);
      const json = await response.json();
      return this.unwrap(json) as T;
    } finally {
      clearTimeout(timer);
    }
  }

  private async requestVoid(
    method: string,
    path: string,
    options: {
      timeout?: number;
    } = {},
  ): Promise<void> {
    const url = new URL(path, this.baseUrl);
    const controller = new AbortController();
    const timeoutMs = options.timeout ?? 60_000;
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(url.toString(), {
        method,
        headers: this.authHeaders(),
        signal: controller.signal,
      });
      await this.raiseForStatus(response);
    } finally {
      clearTimeout(timer);
    }
  }

  private unwrap(body: unknown): unknown {
    if (body && typeof body === 'object' && 'data' in body) {
      return (body as Record<string, unknown>).data;
    }
    return body;
  }

  private async raiseForStatus(response: Response): Promise<void> {
    if (response.ok) return;

    let detail: string;
    try {
      const body = await response.json();
      const error = body?.error;
      if (error && typeof error === 'object' && 'message' in error) {
        detail = error.message;
      } else {
        detail = body?.detail ?? response.statusText;
      }
    } catch {
      detail = response.statusText;
    }

    throw new LonaClientError(`Lona API error ${response.status}: ${detail}`, response.status);
  }

  async register(): Promise<LonaRegistrationResponse> {
    const body = {
      agent_id: this.agentId,
      agent_name: this.agentName,
      source: 'trade-nexus',
      expires_in_days: this.tokenTtlDays,
    };

    const url = new URL('/api/v1/agents/register', this.baseUrl);
    const response = await fetch(url.toString(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Agent-Registration-Secret': this.registrationSecret,
      },
      body: JSON.stringify(body),
    });

    await this.raiseForStatus(response);
    const json = await response.json();
    const data = this.unwrap(json) as LonaRegistrationResponse;
    this.token = data.token;
    return data;
  }

  async requestInvite(): Promise<{ invite_code: string }> {
    const url = new URL('/api/v1/agents/request-invite', this.baseUrl);
    const response = await fetch(url.toString(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agent_id: this.agentId,
        agent_name: this.agentName,
        source: 'trade-nexus',
      }),
    });

    await this.raiseForStatus(response);
    const json = await response.json();
    return this.unwrap(json) as { invite_code: string };
  }

  async registerWithInviteCode(inviteCode: string): Promise<LonaRegistrationResponse> {
    const body = {
      agent_id: this.agentId,
      agent_name: this.agentName,
      source: 'trade-nexus',
      invite_code: inviteCode,
      expires_in_days: this.tokenTtlDays,
    };

    const url = new URL('/api/v1/agents/register', this.baseUrl);
    const response = await fetch(url.toString(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    await this.raiseForStatus(response);
    const json = await response.json();
    const data = this.unwrap(json) as LonaRegistrationResponse;
    this.token = data.token;
    return data;
  }

  async createStrategyFromDescription(
    description: string,
    name?: string,
    provider?: string,
    model?: string,
  ): Promise<LonaStrategyFromDescriptionResponse> {
    const body: Record<string, string> = { description };
    if (name) body.name = name;
    if (provider) body.provider = provider;
    if (model) body.model = model;

    return this.request<LonaStrategyFromDescriptionResponse>(
      'POST',
      '/api/v1/agent/strategy/create',
      { body, timeout: 180_000 },
    );
  }

  async createStrategy(name: string, code: string, description?: string): Promise<{ id: string }> {
    return this.request<{ id: string }>('POST', '/api/v1/strategies', {
      body: { name, code, description, version: '1.0.0', language: 'python' },
    });
  }

  async listStrategies(skip = 0, limit = 50): Promise<LonaStrategy[]> {
    const data = await this.request<{ items: LonaStrategy[] }>('GET', '/api/v1/strategies', {
      params: { skip, limit },
    });
    return data.items ?? [];
  }

  async getStrategy(strategyId: string): Promise<LonaStrategy> {
    return this.request<LonaStrategy>('GET', `/api/v1/strategies/${strategyId}`);
  }

  async getStrategyCode(strategyId: string): Promise<string> {
    const data = await this.request<{ code: string }>(
      'GET',
      `/api/v1/strategies/${strategyId}/code`,
    );
    return data.code ?? '';
  }

  async listSymbols(isGlobal = false, limit = 50, skip = 0): Promise<LonaSymbol[]> {
    const params: Record<string, string | number | boolean> = { skip, limit };
    if (isGlobal) params.is_global = true;
    const data = await this.request<{ items: LonaSymbol[] }>('GET', '/api/v1/symbols', { params });
    return data.items ?? [];
  }

  async getSymbol(symbolId: string): Promise<LonaSymbol> {
    return this.request<LonaSymbol>('GET', `/api/v1/symbols/${symbolId}`);
  }

  async deleteSymbol(symbolId: string): Promise<void> {
    return this.requestVoid('DELETE', `/api/v1/symbols/${symbolId}`);
  }

  async findSymbolByName(name: string): Promise<LonaSymbol | null> {
    // No server-side filter by name — paginate through all user symbols.
    const PAGE_SIZE = 50;
    let skip = 0;
    for (;;) {
      const page = await this.listSymbols(false, PAGE_SIZE, skip);
      const match = page.find((s) => s.name === name);
      if (match) return match;
      if (page.length < PAGE_SIZE) break;
      skip += PAGE_SIZE;
    }
    return null;
  }

  async uploadSymbol(csvContent: Blob, metadata: Record<string, unknown>): Promise<{ id: string }> {
    const formData = new FormData();
    formData.append('file', csvContent, 'data.csv');
    formData.append('metadata', JSON.stringify(metadata));

    const url = new URL('/api/v1/symbols', this.baseUrl);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60_000);

    try {
      const response = await fetch(url.toString(), {
        method: 'POST',
        headers: {
          'X-API-Key': this.token,
          'X-User-Id': this.agentId,
        },
        body: formData,
        signal: controller.signal,
      });
      await this.raiseForStatus(response);
      const json = await response.json();
      return this.unwrap(json) as { id: string };
    } finally {
      clearTimeout(timer);
    }
  }

  async downloadMarketData(
    symbol: string,
    interval: string,
    startDate: string,
    endDate: string,
  ): Promise<LonaSymbol> {
    const candles = await this.fetchBinanceKlines(symbol, interval, startDate, endDate);
    const csvContent = this.candlesToCsv(candles);
    const nameStart = startDate.replace(/-/g, '');
    const nameEnd = endDate.replace(/-/g, '');
    const metadata = {
      data_type: 'ohlcv',
      name: `${symbol}_${interval}_${nameStart}_${nameEnd}`,
      exchange: 'BINANCE',
      asset_class: 'crypto',
      quote_currency: 'USD',
      column_mapping: {
        timestamp: 'timestamp',
        open: 'open',
        high: 'high',
        low: 'low',
        close: 'close',
        volume: 'volume',
      },
      frequency: interval,
      timezone: 'UTC',
      description: `${symbol} ${interval} candles from Binance (${startDate} to ${endDate})`,
    };

    const data = await this.uploadSymbol(new Blob([csvContent], { type: 'text/csv' }), metadata);

    if (data.id) {
      return this.getSymbol(data.id);
    }
    return { id: '', name: symbol } as LonaSymbol;
  }

  private async fetchBinanceKlines(
    symbol: string,
    interval: string,
    startDate: string,
    endDate: string,
  ): Promise<unknown[][]> {
    const MAX_PAGES = 100;
    const startMs = new Date(startDate).getTime();
    const endMs = new Date(endDate).getTime();
    const allCandles: unknown[][] = [];
    let currentStart = startMs;
    let pages = 0;

    while (currentStart < endMs && pages < MAX_PAGES) {
      pages++;
      const url = new URL(BINANCE_KLINES_URL);
      url.searchParams.set('symbol', symbol.toUpperCase());
      url.searchParams.set('interval', interval);
      url.searchParams.set('startTime', String(currentStart));
      url.searchParams.set('endTime', String(endMs));
      url.searchParams.set('limit', String(BINANCE_MAX_LIMIT));

      const response = await fetch(url.toString());
      if (!response.ok) {
        throw new LonaClientError(
          `Binance API error ${response.status}: ${await response.text()}`,
          response.status,
        );
      }

      const batch: unknown[][] = await response.json();
      if (!batch.length) break;

      allCandles.push(...batch);

      const lastCloseTime = batch[batch.length - 1][6] as number;
      currentStart = lastCloseTime + 1;

      if (batch.length < BINANCE_MAX_LIMIT) break;
    }

    return allCandles;
  }

  private candlesToCsv(candles: unknown[][]): string {
    const rows = ['timestamp,open,high,low,close,volume'];
    for (const candle of candles) {
      const ts = new Date(candle[0] as number)
        .toISOString()
        .replace('T', ' ')
        .replace(/\.\d+Z$/, '');
      rows.push(`${ts},${candle[1]},${candle[2]},${candle[3]},${candle[4]},${candle[5]}`);
    }
    return rows.join('\n');
  }

  async runBacktest(request: LonaBacktestRequest): Promise<LonaBacktestResponse> {
    return this.request<LonaBacktestResponse>('POST', '/api/v1/runner/run', {
      body: request,
    });
  }

  async getReportStatus(reportId: string): Promise<LonaReportStatus> {
    return this.request<LonaReportStatus>('GET', `/api/v1/reports/${reportId}/status`);
  }

  async getReport(reportId: string): Promise<LonaReport> {
    return this.request<LonaReport>('GET', `/api/v1/reports/${reportId}`);
  }

  async getFullReport(reportId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('GET', `/api/v1/reports/${reportId}/full`, {
      timeout: 60_000,
    });
  }

  async waitForReport(
    reportId: string,
    timeout = 300_000,
    pollInterval = 5_000,
  ): Promise<LonaReport> {
    let elapsed = 0;
    while (elapsed < timeout) {
      const status = await this.getReportStatus(reportId);

      if (status.status === 'COMPLETED') {
        return this.getReport(reportId);
      }
      if (status.status === 'FAILED') {
        const report = await this.getReport(reportId);
        throw new LonaClientError(
          `Backtest report ${reportId} failed: ${report.error ?? 'unknown error'}`,
        );
      }

      await new Promise((r) => setTimeout(r, pollInterval));
      elapsed += pollInterval;
    }

    throw new LonaClientError(`Timed out waiting for report ${reportId} after ${timeout / 1000}s`);
  }
}

let _client: LonaClient | null = null;

export function getLonaClient(): LonaClient {
  if (!_client) {
    _client = new LonaClient();
  }
  return _client;
}
