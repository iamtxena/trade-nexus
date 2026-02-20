import { afterEach, beforeEach, describe, expect, mock, spyOn, test } from 'bun:test';

import { LonaClient, LonaClientError } from '../client';
import type { LonaSymbol } from '../types';

// Store original fetch so we can restore it
const originalFetch = globalThis.fetch;

// Helper to create a mock Response
function mockResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: { 'Content-Type': 'application/json' },
  });
}

function mockVoidResponse(status = 204): Response {
  return new Response(null, {
    status,
    statusText: 'No Content',
  });
}

function createClient(
  overrides?: Partial<{
    gatewayUrl: string;
    agentId: string;
    agentName: string;
    registrationSecret: string;
    token: string;
    tokenTtlDays: number;
  }>,
): LonaClient {
  return new LonaClient({
    gatewayUrl: 'https://test-gateway.example.com',
    agentId: 'test-agent',
    agentName: 'Test Agent',
    registrationSecret: 'test-secret',
    token: 'test-token',
    tokenTtlDays: 30,
    ...overrides,
  });
}

describe('LonaClient', () => {
  let fetchMock: ReturnType<typeof mock>;

  beforeEach(() => {
    fetchMock = mock(() => Promise.resolve(mockResponse({})));
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe('deleteSymbol', () => {
    test('sends DELETE request with correct URL', async () => {
      fetchMock = mock(() => Promise.resolve(mockVoidResponse()));
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();
      await client.deleteSymbol('sym-123');

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toBe('https://test-gateway.example.com/api/v1/symbols/sym-123');
      expect(options.method).toBe('DELETE');
    });

    test('includes auth headers', async () => {
      fetchMock = mock(() => Promise.resolve(mockVoidResponse()));
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient({ token: 'my-token', agentId: 'my-agent' });
      await client.deleteSymbol('sym-456');

      const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Record<string, string>;
      expect(headers['X-API-Key']).toBe('my-token');
      expect(headers['X-User-Id']).toBe('my-agent');
    });

    test('throws LonaClientError on non-OK response', async () => {
      fetchMock = mock(() =>
        Promise.resolve(
          new Response(JSON.stringify({ detail: 'Not found' }), {
            status: 404,
            statusText: 'Not Found',
          }),
        ),
      );
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();

      try {
        await client.deleteSymbol('nonexistent');
        expect(true).toBe(false); // Should not reach here
      } catch (error) {
        expect(error).toBeInstanceOf(LonaClientError);
        expect((error as LonaClientError).statusCode).toBe(404);
        expect((error as LonaClientError).message).toContain('404');
      }
    });

    test('returns void on success (no JSON parsing)', async () => {
      fetchMock = mock(() => Promise.resolve(mockVoidResponse()));
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();
      const result = await client.deleteSymbol('sym-789');

      expect(result).toBeUndefined();
    });
  });

  describe('findSymbolByName', () => {
    const sampleSymbols: LonaSymbol[] = [
      {
        id: 'id-1',
        name: 'BTCUSDT_1h_20250101_20250601',
        description: 'BTC',
        is_global: false,
        data_range: null,
        frequencies: ['1h'],
        type_metadata: null,
        created_at: '2025-01-01',
        updated_at: '2025-01-01',
      },
      {
        id: 'id-2',
        name: 'ETHUSDT_1h_20250101_20250601',
        description: 'ETH',
        is_global: false,
        data_range: null,
        frequencies: ['1h'],
        type_metadata: null,
        created_at: '2025-01-01',
        updated_at: '2025-01-01',
      },
    ];

    test('returns matching symbol when found', async () => {
      fetchMock = mock(() => Promise.resolve(mockResponse({ data: { items: sampleSymbols } })));
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();
      const result = await client.findSymbolByName('BTCUSDT_1h_20250101_20250601');

      expect(result).not.toBeNull();
      expect(result!.id).toBe('id-1');
      expect(result!.name).toBe('BTCUSDT_1h_20250101_20250601');
    });

    test('returns null when no match found', async () => {
      fetchMock = mock(() => Promise.resolve(mockResponse({ data: { items: sampleSymbols } })));
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();
      const result = await client.findSymbolByName('SOLUSDT_1h_20250101_20250601');

      expect(result).toBeNull();
    });

    test('returns null when no symbols exist', async () => {
      fetchMock = mock(() => Promise.resolve(mockResponse({ data: { items: [] } })));
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();
      const result = await client.findSymbolByName('anything');

      expect(result).toBeNull();
    });

    test('paginates with limit=50 instead of one large request', async () => {
      fetchMock = mock(() => Promise.resolve(mockResponse({ data: { items: [] } })));
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();
      await client.findSymbolByName('test');

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toContain('limit=50');
      expect(url).toContain('skip=0');
    });

    test('paginates through multiple pages until match found', async () => {
      const page1 = Array.from({ length: 50 }, (_, i) => ({
        id: `id-${i}`,
        name: `SYM_${i}`,
        description: '',
        is_global: false,
        data_range: null,
        frequencies: [],
        type_metadata: null,
        created_at: '',
        updated_at: '',
      }));
      const page2 = [
        {
          id: 'target-id',
          name: 'TARGET_SYMBOL',
          description: '',
          is_global: false,
          data_range: null,
          frequencies: [],
          type_metadata: null,
          created_at: '',
          updated_at: '',
        },
      ];

      let callCount = 0;
      fetchMock = mock(() => {
        callCount++;
        if (callCount === 1) return Promise.resolve(mockResponse({ data: { items: page1 } }));
        return Promise.resolve(mockResponse({ data: { items: page2 } }));
      });
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();
      const result = await client.findSymbolByName('TARGET_SYMBOL');

      expect(result).not.toBeNull();
      expect(result!.id).toBe('target-id');
      expect(fetchMock).toHaveBeenCalledTimes(2);

      const [url2] = (fetchMock.mock.calls as Array<[string, RequestInit]>)[1];
      expect(url2).toContain('skip=50');
      expect(url2).toContain('limit=50');
    });
  });

  describe('requestInvite', () => {
    test('sends POST request to correct endpoint', async () => {
      fetchMock = mock(() => Promise.resolve(mockResponse({ data: { invite_code: 'INV-12345' } })));
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient({ agentId: 'my-agent', agentName: 'My Agent' });
      const result = await client.requestInvite();

      expect(result.invite_code).toBe('INV-12345');

      expect(fetchMock).toHaveBeenCalledTimes(1);
      const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toBe('https://test-gateway.example.com/api/v1/agents/request-invite');
      expect(options.method).toBe('POST');
    });

    test('sends correct body with agent info', async () => {
      fetchMock = mock(() => Promise.resolve(mockResponse({ data: { invite_code: 'INV-ABCDE' } })));
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient({ agentId: 'nexus-1', agentName: 'Nexus Agent' });
      await client.requestInvite();

      const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      const body = JSON.parse(options.body as string);
      expect(body.agent_id).toBe('nexus-1');
      expect(body.agent_name).toBe('Nexus Agent');
      expect(body.source).toBe('trade-nexus');
    });

    test('sends Content-Type header without auth headers', async () => {
      fetchMock = mock(() => Promise.resolve(mockResponse({ data: { invite_code: 'INV-XYZ' } })));
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();
      await client.requestInvite();

      const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Record<string, string>;
      expect(headers['Content-Type']).toBe('application/json');
      // requestInvite does NOT use authHeaders, so no X-API-Key or X-User-Id
      expect(headers['X-API-Key']).toBeUndefined();
      expect(headers['X-User-Id']).toBeUndefined();
    });

    test('throws on error response', async () => {
      fetchMock = mock(() =>
        Promise.resolve(
          new Response(JSON.stringify({ detail: 'Rate limited' }), {
            status: 429,
            statusText: 'Too Many Requests',
          }),
        ),
      );
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();

      try {
        await client.requestInvite();
        expect(true).toBe(false);
      } catch (error) {
        expect(error).toBeInstanceOf(LonaClientError);
        expect((error as LonaClientError).statusCode).toBe(429);
      }
    });
  });

  describe('registerWithInviteCode', () => {
    test('sends POST to register endpoint with invite_code in body', async () => {
      fetchMock = mock(() =>
        Promise.resolve(
          mockResponse({
            data: {
              token: 'new-token',
              partner_id: 'p-1',
              partner_name: 'Test',
              permissions: ['read', 'write'],
              expires_at: '2026-03-01',
            },
          }),
        ),
      );
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient({ agentId: 'nexus', agentName: 'Nexus' });
      const result = await client.registerWithInviteCode('INV-CODE-123');

      expect(result.token).toBe('new-token');
      expect(result.partner_id).toBe('p-1');

      const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toBe('https://test-gateway.example.com/api/v1/agents/register');
      expect(options.method).toBe('POST');

      const body = JSON.parse(options.body as string);
      expect(body.invite_code).toBe('INV-CODE-123');
      expect(body.agent_id).toBe('nexus');
      expect(body.agent_name).toBe('Nexus');
      expect(body.source).toBe('trade-nexus');
      expect(body.expires_in_days).toBe(30);
    });

    test('does NOT include registration secret header', async () => {
      fetchMock = mock(() =>
        Promise.resolve(
          mockResponse({
            data: {
              token: 't',
              partner_id: 'p',
              partner_name: 'n',
              permissions: [],
              expires_at: '',
            },
          }),
        ),
      );
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient({ registrationSecret: 'should-not-be-sent' });
      await client.registerWithInviteCode('INV-123');

      const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Record<string, string>;
      expect(headers['X-Agent-Registration-Secret']).toBeUndefined();
      expect(headers['Content-Type']).toBe('application/json');
    });

    test('updates internal token after successful registration', async () => {
      fetchMock = mock(() =>
        Promise.resolve(
          mockResponse({
            data: {
              token: 'updated-token-value',
              partner_id: 'p',
              partner_name: 'n',
              permissions: [],
              expires_at: '',
            },
          }),
        ),
      );
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient({ token: 'old-token' });
      await client.registerWithInviteCode('INV-456');

      // After registration, subsequent calls should use the new token.
      // We verify by making another call and checking the auth header.
      fetchMock = mock(() => Promise.resolve(mockResponse({ data: { items: [] } })));
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      await client.listSymbols();

      const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      const headers = options.headers as Record<string, string>;
      expect(headers['X-API-Key']).toBe('updated-token-value');
    });
  });

  describe('downloadMarketData - smart naming', () => {
    test('generates name in SYMBOL_INTERVAL_YYYYMMDD_YYYYMMDD format', async () => {
      // We need to intercept the uploadSymbol call to verify the metadata name.
      // Since downloadMarketData calls fetchBinanceKlines first, then uploadSymbol,
      // we need to mock fetch to handle both calls.
      let uploadedMetadata: Record<string, unknown> | null = null;

      fetchMock = mock((url: string, options?: RequestInit) => {
        // Binance klines call
        if (url.includes('binance.com')) {
          return Promise.resolve(
            new Response(JSON.stringify([]), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          );
        }
        // uploadSymbol (POST /api/v1/symbols) - multipart form data
        if (url.includes('/api/v1/symbols') && options?.method === 'POST') {
          // Extract metadata from FormData
          const body = options.body as FormData;
          if (body && typeof body.get === 'function') {
            const metadataStr = body.get('metadata') as string;
            if (metadataStr) {
              uploadedMetadata = JSON.parse(metadataStr);
            }
          }
          return Promise.resolve(mockResponse({ data: { id: 'new-sym-id' } }));
        }
        // getSymbol (GET /api/v1/symbols/{id})
        if (url.includes('/api/v1/symbols/new-sym-id')) {
          return Promise.resolve(
            mockResponse({
              data: {
                id: 'new-sym-id',
                name: 'BTCUSDT_1h_20250101_20250601',
                description: 'test',
                is_global: false,
                data_range: null,
                frequencies: ['1h'],
                type_metadata: null,
                created_at: '2025-01-01',
                updated_at: '2025-01-01',
              },
            }),
          );
        }
        return Promise.resolve(mockResponse({}));
      });
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();
      const result = await client.downloadMarketData('BTCUSDT', '1h', '2025-01-01', '2025-06-01');

      expect(result.id).toBe('new-sym-id');

      // Verify metadata name format
      expect(uploadedMetadata).not.toBeNull();
      expect(uploadedMetadata!.name).toBe('BTCUSDT_1h_20250101_20250601');
    });

    test('strips dashes from dates in name', async () => {
      let uploadedMetadata: Record<string, unknown> | null = null;

      fetchMock = mock((url: string, options?: RequestInit) => {
        if (url.includes('binance.com')) {
          return Promise.resolve(
            new Response(JSON.stringify([]), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          );
        }
        if (url.includes('/api/v1/symbols') && options?.method === 'POST') {
          const body = options.body as FormData;
          if (body && typeof body.get === 'function') {
            const metadataStr = body.get('metadata') as string;
            if (metadataStr) {
              uploadedMetadata = JSON.parse(metadataStr);
            }
          }
          return Promise.resolve(mockResponse({ data: { id: 'sym-new' } }));
        }
        if (url.includes('/api/v1/symbols/sym-new')) {
          return Promise.resolve(
            mockResponse({
              data: {
                id: 'sym-new',
                name: 'ETHUSDT_4h_20240315_20241215',
                description: '',
                is_global: false,
                data_range: null,
                frequencies: ['4h'],
                type_metadata: null,
                created_at: '',
                updated_at: '',
              },
            }),
          );
        }
        return Promise.resolve(mockResponse({}));
      });
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();
      await client.downloadMarketData('ETHUSDT', '4h', '2024-03-15', '2024-12-15');

      expect(uploadedMetadata).not.toBeNull();
      expect(uploadedMetadata!.name).toBe('ETHUSDT_4h_20240315_20241215');
    });

    test('includes symbol, interval, exchange, and description in metadata', async () => {
      let uploadedMetadata: Record<string, unknown> | null = null;

      fetchMock = mock((url: string, options?: RequestInit) => {
        if (url.includes('binance.com')) {
          return Promise.resolve(
            new Response(JSON.stringify([]), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          );
        }
        if (url.includes('/api/v1/symbols') && options?.method === 'POST') {
          const body = options.body as FormData;
          if (body && typeof body.get === 'function') {
            const metadataStr = body.get('metadata') as string;
            if (metadataStr) {
              uploadedMetadata = JSON.parse(metadataStr);
            }
          }
          return Promise.resolve(mockResponse({ data: { id: 'id-x' } }));
        }
        if (url.includes('/api/v1/symbols/id-x')) {
          return Promise.resolve(
            mockResponse({
              data: {
                id: 'id-x',
                name: 'test',
                description: '',
                is_global: false,
                data_range: null,
                frequencies: [],
                type_metadata: null,
                created_at: '',
                updated_at: '',
              },
            }),
          );
        }
        return Promise.resolve(mockResponse({}));
      });
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();
      await client.downloadMarketData('SOLUSDT', '15m', '2025-02-01', '2025-02-10');

      expect(uploadedMetadata).not.toBeNull();
      const meta = uploadedMetadata!;
      expect(meta.data_type).toBe('ohlcv');
      expect(meta.exchange).toBe('BINANCE');
      expect(meta.asset_class).toBe('crypto');
      expect(meta.frequency).toBe('15m');
      expect(meta.description).toBe('SOLUSDT 15m candles from Binance (2025-02-01 to 2025-02-10)');
    });
  });

  describe('createStrategyFromDescription retry behavior', () => {
    test('retries once with a unique name when API returns resource already exists', async () => {
      let callCount = 0;
      let firstBody: Record<string, unknown> | null = null;
      let secondBody: Record<string, unknown> | null = null;

      fetchMock = mock((_url: string, options?: RequestInit) => {
        callCount++;
        if (callCount === 1) {
          firstBody = JSON.parse(String(options?.body));
          return Promise.resolve(
            new Response(JSON.stringify({ error: { message: 'Resource already exists' } }), {
              status: 409,
              statusText: 'Conflict',
            }),
          );
        }

        secondBody = JSON.parse(String(options?.body));
        return Promise.resolve(
          mockResponse({
            data: {
              strategyId: 'strategy-2',
              name: 'retry-strategy',
              code: 'print("ok")',
              explanation: 'test',
            },
          }),
        );
      });
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();
      const result = await client.createStrategyFromDescription('RSI mean reversion on BTCUSDT');

      expect(result.strategyId).toBe('strategy-2');
      expect(callCount).toBe(2);
      expect(firstBody?.['name']).toBeUndefined();
      const retryName = secondBody?.['name'];
      expect(typeof retryName).toBe('string');
      expect(String(retryName).length).toBeGreaterThan(0);
    });
  });

  describe('backtest failure messages', () => {
    test('adds categorized CODE_ERROR context with stderr snippet', async () => {
      fetchMock = mock((url: string) => {
        if (url.includes('/api/v1/reports/rpt-1/status')) {
          return Promise.resolve(mockResponse({ data: { status: 'FAILED', progress: 1 } }));
        }
        if (url.includes('/api/v1/reports/rpt-1/full')) {
          return Promise.resolve(
            mockResponse({
              data: {
                stderr: 'Traceback ... NameError: period is not defined',
              },
            }),
          );
        }
        if (url.includes('/api/v1/reports/rpt-1')) {
          return Promise.resolve(
            mockResponse({
              data: {
                id: 'rpt-1',
                strategy_id: 'str-1',
                status: 'FAILED',
                name: 'test',
                description: '',
                created_at: '',
                updated_at: '',
                total_stats: null,
                error: "NameError: name 'period' is not defined",
              },
            }),
          );
        }
        return Promise.resolve(mockResponse({}));
      });
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();

      try {
        await client.waitForReport('rpt-1', 10_000, 1);
        expect(true).toBe(false);
      } catch (error) {
        expect(error).toBeInstanceOf(LonaClientError);
        const message = (error as LonaClientError).message;
        expect(message).toContain('[CODE_ERROR]');
        expect(message).toContain('stderr:');
        expect(message).toContain('period is not defined');
      }
    });

    test('adds data ownership hint when runBacktest returns data not found', async () => {
      fetchMock = mock(() =>
        Promise.resolve(
          new Response(JSON.stringify({ detail: 'Data abc123 not found' }), {
            status: 404,
            statusText: 'Not Found',
            headers: { 'Content-Type': 'application/json' },
          }),
        ),
      );
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient();
      try {
        await client.runBacktest({
          strategy_id: 's-1',
          data_ids: ['abc123'],
          start_date: '2025-01-01',
          end_date: '2025-02-01',
          simulation_parameters: {
            initial_cash: 100000,
            commission_schema: { commission: 0.001, leverage: 1 },
            buy_on_close: true,
          },
        });
        expect(true).toBe(false);
      } catch (error) {
        expect(error).toBeInstanceOf(LonaClientError);
        expect((error as LonaClientError).message).toContain('same Lona user/token');
      }
    });
  });

  describe('LonaClientError', () => {
    test('has correct name and statusCode', () => {
      const error = new LonaClientError('test error', 500);
      expect(error.name).toBe('LonaClientError');
      expect(error.statusCode).toBe(500);
      expect(error.message).toBe('test error');
    });

    test('statusCode defaults to null', () => {
      const error = new LonaClientError('no status');
      expect(error.statusCode).toBeNull();
    });
  });

  describe('register (secret-based)', () => {
    test('sends X-Agent-Registration-Secret header', async () => {
      fetchMock = mock(() =>
        Promise.resolve(
          mockResponse({
            data: {
              token: 'reg-token',
              partner_id: 'p-id',
              partner_name: 'name',
              permissions: [],
              expires_at: '2026-12-31',
            },
          }),
        ),
      );
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const client = createClient({ registrationSecret: 'my-secret-key' });
      await client.register();

      const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toBe('https://test-gateway.example.com/api/v1/agents/register');
      const headers = options.headers as Record<string, string>;
      expect(headers['X-Agent-Registration-Secret']).toBe('my-secret-key');
    });
  });
});
