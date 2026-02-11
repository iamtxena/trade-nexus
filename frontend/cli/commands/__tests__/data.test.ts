import { afterEach, beforeEach, describe, expect, mock, spyOn, test } from 'bun:test';

import { LonaClient } from '../../../src/lib/lona/client';
import type { LonaSymbol } from '../../../src/lib/lona/types';

// Store originals
const originalFetch = globalThis.fetch;
const originalExit = process.exit;
const originalEnv = { ...process.env };

// Mock console to suppress CLI output during tests
let consoleLogSpy: ReturnType<typeof spyOn>;
let consoleErrorSpy: ReturnType<typeof spyOn>;
let stdoutWriteSpy: ReturnType<typeof spyOn>;

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

const sampleSymbol: LonaSymbol = {
  id: 'sym-abc-123',
  name: 'BTCUSDT_1h_20250101_20250601',
  description: 'BTC 1h candles',
  is_global: false,
  data_range: {
    start_timestamp: '2025-01-01',
    end_timestamp: '2025-06-01',
  },
  frequencies: ['1h'],
  type_metadata: {
    data_type: 'ohlcv',
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
  },
  created_at: '2025-01-01',
  updated_at: '2025-01-01',
};

describe('data command', () => {
  let fetchMock: ReturnType<typeof mock>;

  beforeEach(() => {
    // Suppress console output from CLI
    consoleLogSpy = spyOn(console, 'log').mockImplementation(() => {});
    consoleErrorSpy = spyOn(console, 'error').mockImplementation(() => {});
    stdoutWriteSpy = spyOn(process.stdout, 'write').mockImplementation(() => true);

    // Set required env vars for validateConfig
    process.env.LONA_AGENT_TOKEN = 'test-token';
    process.env.LONA_GATEWAY_URL = 'https://test-gateway.example.com';
    process.env.LONA_AGENT_ID = 'test-agent';

    // Mock process.exit to throw instead of actually exiting
    process.exit = mock((code?: number) => {
      throw new Error(`process.exit(${code})`);
    }) as unknown as typeof process.exit;
  });

  afterEach(() => {
    consoleLogSpy.mockRestore();
    consoleErrorSpy.mockRestore();
    stdoutWriteSpy.mockRestore();
    globalThis.fetch = originalFetch;
    process.exit = originalExit;
    // Restore env
    process.env = { ...originalEnv };
  });

  describe('delete subcommand', () => {
    test('calls deleteSymbol with the provided --id', async () => {
      fetchMock = mock(() => Promise.resolve(mockVoidResponse()));
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      // Dynamic import to pick up mocked env
      const { dataCommand } = await import('../data');
      await dataCommand(['delete', '--id', 'sym-to-delete']);

      // Verify DELETE was called
      expect(fetchMock).toHaveBeenCalled();
      const calls = fetchMock.mock.calls as Array<[string, RequestInit]>;
      const deleteCall = calls.find(
        ([url, opts]) => url.includes('/api/v1/symbols/sym-to-delete') && opts.method === 'DELETE',
      );
      expect(deleteCall).toBeDefined();
    });

    test('exits with error when --id is missing', async () => {
      const { dataCommand } = await import('../data');

      try {
        await dataCommand(['delete']);
        expect(true).toBe(false); // Should not reach
      } catch (error) {
        expect((error as Error).message).toBe('process.exit(1)');
      }
    });
  });

  describe('download --force flag', () => {
    test('deletes existing symbol before downloading when --force is set', async () => {
      const callLog: Array<{ url: string; method: string }> = [];

      fetchMock = mock((url: string, options?: RequestInit) => {
        const method = options?.method ?? 'GET';
        callLog.push({ url, method });

        // listSymbols call (findSymbolByName)
        if (url.includes('/api/v1/symbols') && method === 'GET' && !url.includes('sym-abc-123')) {
          return Promise.resolve(mockResponse({ data: { items: [sampleSymbol] } }));
        }
        // deleteSymbol call
        if (url.includes('/api/v1/symbols/sym-abc-123') && method === 'DELETE') {
          return Promise.resolve(mockVoidResponse());
        }
        // Binance klines
        if (url.includes('binance.com')) {
          return Promise.resolve(
            new Response(JSON.stringify([]), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          );
        }
        // uploadSymbol (POST /api/v1/symbols) - form data
        if (url.includes('/api/v1/symbols') && method === 'POST') {
          return Promise.resolve(mockResponse({ data: { id: 'new-sym' } }));
        }
        // getSymbol after upload
        if (url.includes('/api/v1/symbols/new-sym') && method === 'GET') {
          return Promise.resolve(
            mockResponse({
              data: {
                ...sampleSymbol,
                id: 'new-sym',
              },
            }),
          );
        }
        return Promise.resolve(mockResponse({}));
      });
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const { dataCommand } = await import('../data');
      await dataCommand([
        'download',
        '--symbol',
        'BTCUSDT',
        '--interval',
        '1h',
        '--start',
        '2025-01-01',
        '--end',
        '2025-06-01',
        '--force',
      ]);

      // Verify the sequence: first findSymbolByName (GET), then deleteSymbol (DELETE),
      // then Binance fetch, then upload
      const deleteCall = callLog.find(
        (c) => c.url.includes('/api/v1/symbols/sym-abc-123') && c.method === 'DELETE',
      );
      expect(deleteCall).toBeDefined();

      // DELETE should happen before the Binance call
      const deleteIdx = callLog.findIndex(
        (c) => c.url.includes('sym-abc-123') && c.method === 'DELETE',
      );
      const binanceIdx = callLog.findIndex((c) => c.url.includes('binance.com'));
      expect(deleteIdx).toBeLessThan(binanceIdx);
    });

    test('skips delete when --force is set but no existing symbol found', async () => {
      const callLog: Array<{ url: string; method: string }> = [];

      fetchMock = mock((url: string, options?: RequestInit) => {
        const method = options?.method ?? 'GET';
        callLog.push({ url, method });

        // listSymbols returns empty (no matching symbol)
        if (url.includes('/api/v1/symbols') && method === 'GET' && url.includes('limit=200')) {
          return Promise.resolve(mockResponse({ data: { items: [] } }));
        }
        if (url.includes('binance.com')) {
          return Promise.resolve(
            new Response(JSON.stringify([]), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          );
        }
        if (url.includes('/api/v1/symbols') && method === 'POST') {
          return Promise.resolve(mockResponse({ data: { id: 'brand-new' } }));
        }
        if (url.includes('/api/v1/symbols/brand-new') && method === 'GET') {
          return Promise.resolve(
            mockResponse({
              data: {
                ...sampleSymbol,
                id: 'brand-new',
                name: 'BTCUSDT_1h_20250101_20250601',
              },
            }),
          );
        }
        return Promise.resolve(mockResponse({}));
      });
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const { dataCommand } = await import('../data');
      await dataCommand([
        'download',
        '--symbol',
        'BTCUSDT',
        '--interval',
        '1h',
        '--start',
        '2025-01-01',
        '--end',
        '2025-06-01',
        '--force',
      ]);

      // No DELETE call should have been made
      const deleteCalls = callLog.filter((c) => c.method === 'DELETE');
      expect(deleteCalls.length).toBe(0);
    });

    test('does not try to delete when --force is not set', async () => {
      const callLog: Array<{ url: string; method: string }> = [];

      fetchMock = mock((url: string, options?: RequestInit) => {
        const method = options?.method ?? 'GET';
        callLog.push({ url, method });

        if (url.includes('binance.com')) {
          return Promise.resolve(
            new Response(JSON.stringify([]), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          );
        }
        if (url.includes('/api/v1/symbols') && method === 'POST') {
          return Promise.resolve(mockResponse({ data: { id: 'sym-123' } }));
        }
        if (url.includes('/api/v1/symbols/sym-123') && method === 'GET') {
          return Promise.resolve(
            mockResponse({
              data: {
                ...sampleSymbol,
                id: 'sym-123',
              },
            }),
          );
        }
        return Promise.resolve(mockResponse({}));
      });
      globalThis.fetch = fetchMock as unknown as typeof fetch;

      const { dataCommand } = await import('../data');
      await dataCommand([
        'download',
        '--symbol',
        'BTCUSDT',
        '--interval',
        '1h',
        '--start',
        '2025-01-01',
        '--end',
        '2025-06-01',
      ]);

      // No DELETE or findSymbolByName (list with limit=200) call
      const deleteCalls = callLog.filter((c) => c.method === 'DELETE');
      expect(deleteCalls.length).toBe(0);

      // No listSymbols call for findSymbolByName (limit=200)
      const findCalls = callLog.filter((c) => c.url.includes('limit=200') && c.method === 'GET');
      expect(findCalls.length).toBe(0);
    });
  });

  describe('download required args', () => {
    test('exits with error when --symbol is missing', async () => {
      const { dataCommand } = await import('../data');

      try {
        await dataCommand(['download', '--start', '2025-01-01', '--end', '2025-06-01']);
        expect(true).toBe(false);
      } catch (error) {
        expect((error as Error).message).toBe('process.exit(1)');
      }
    });

    test('exits with error when --start is missing', async () => {
      const { dataCommand } = await import('../data');

      try {
        await dataCommand(['download', '--symbol', 'BTCUSDT', '--end', '2025-06-01']);
        expect(true).toBe(false);
      } catch (error) {
        expect((error as Error).message).toBe('process.exit(1)');
      }
    });

    test('exits with error when --end is missing', async () => {
      const { dataCommand } = await import('../data');

      try {
        await dataCommand(['download', '--symbol', 'BTCUSDT', '--start', '2025-01-01']);
        expect(true).toBe(false);
      } catch (error) {
        expect((error as Error).message).toBe('process.exit(1)');
      }
    });
  });

  describe('subcommand routing', () => {
    test('prints help when no subcommand given', async () => {
      const { dataCommand } = await import('../data');
      await dataCommand([]);

      expect(consoleLogSpy).toHaveBeenCalled();
    });

    test('prints help with --help flag', async () => {
      const { dataCommand } = await import('../data');
      await dataCommand(['--help']);

      expect(consoleLogSpy).toHaveBeenCalled();
    });

    test('exits with error on unknown subcommand', async () => {
      const { dataCommand } = await import('../data');

      try {
        await dataCommand(['foobar']);
        expect(true).toBe(false);
      } catch (error) {
        expect((error as Error).message).toBe('process.exit(1)');
      }
    });
  });
});
