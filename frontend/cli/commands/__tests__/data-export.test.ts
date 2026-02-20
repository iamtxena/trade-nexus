import { afterEach, beforeEach, describe, expect, mock, spyOn, test } from 'bun:test';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import type { OhlcDataPoint } from '../../../src/lib/lona/types';

const originalFetch = globalThis.fetch;
const originalExit = process.exit;
const originalEnv = { ...process.env };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    statusText: status === 200 ? 'OK' : status === 404 ? 'Not Found' : 'Error',
    headers: { 'Content-Type': 'application/json' },
  });
}

const sampleOhlcData: OhlcDataPoint[] = [
  {
    timestamp: '2025-01-01 00:00:00',
    open: 42000,
    high: 42500,
    low: 41800,
    close: 42200,
    volume: 1500,
  },
  {
    timestamp: '2025-01-01 01:00:00',
    open: 42200,
    high: 42800,
    low: 42100,
    close: 42600,
    volume: 1200,
  },
  {
    timestamp: '2025-01-01 02:00:00',
    open: 42600,
    high: 43000,
    low: 42400,
    close: 42900,
    volume: 1800,
  },
];

const sampleSymbol = {
  id: 'sym-export-001',
  name: 'BTCUSDT_1h_20250101_20250601',
  description: 'BTC 1h candles',
  is_global: false,
  file_url: null,
  data_range: { start_timestamp: '2025-01-01', end_timestamp: '2025-06-01' },
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

describe('data export command', () => {
  let consoleLogSpy: ReturnType<typeof spyOn>;
  let consoleErrorSpy: ReturnType<typeof spyOn>;
  let stdoutWriteSpy: ReturnType<typeof spyOn>;
  let fetchMock: ReturnType<typeof mock>;
  let tempDir: string;

  beforeEach(() => {
    tempDir = mkdtempSync(join(tmpdir(), 'nexus-data-export-'));

    consoleLogSpy = spyOn(console, 'log').mockImplementation(() => {});
    consoleErrorSpy = spyOn(console, 'error').mockImplementation(() => {});
    stdoutWriteSpy = spyOn(process.stdout, 'write').mockImplementation(() => true);

    process.env.LONA_AGENT_TOKEN = 'test-token';
    process.env.LONA_GATEWAY_URL = 'https://test-gateway.example.com';
    process.env.LONA_AGENT_ID = 'test-agent';

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
    process.env = { ...originalEnv };
    rmSync(tempDir, { recursive: true, force: true });
  });

  test('exports OHLC data as JSON to stdout', async () => {
    fetchMock = mock((url: string, options?: RequestInit) => {
      const method = options?.method ?? 'GET';
      // getSymbol call
      if (
        url.includes('/api/v1/symbols/sym-export-001') &&
        method === 'GET' &&
        !url.includes('/data')
      ) {
        return Promise.resolve(jsonResponse({ data: sampleSymbol }));
      }
      // getSymbolData call
      if (url.includes('/api/v1/symbols/sym-export-001/data') && method === 'GET') {
        return Promise.resolve(jsonResponse({ data: sampleOhlcData }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { dataCommand } = await import('../data');
    await dataCommand(['export', '--id', 'sym-export-001']);

    const logCalls = consoleLogSpy.mock.calls.map(([arg]: [unknown]) => String(arg));
    const jsonOutput = logCalls.find((c: string) => c.includes('"timestamp"'));
    expect(jsonOutput).toBeDefined();

    const parsed = JSON.parse(jsonOutput!) as OhlcDataPoint[];
    expect(parsed).toHaveLength(3);
    expect(parsed[0].open).toBe(42000);
  });

  test('exports OHLC data as CSV to stdout', async () => {
    fetchMock = mock((url: string, options?: RequestInit) => {
      const method = options?.method ?? 'GET';
      if (
        url.includes('/api/v1/symbols/sym-export-001') &&
        method === 'GET' &&
        !url.includes('/data')
      ) {
        return Promise.resolve(jsonResponse({ data: sampleSymbol }));
      }
      if (url.includes('/api/v1/symbols/sym-export-001/data') && method === 'GET') {
        return Promise.resolve(jsonResponse({ data: sampleOhlcData }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { dataCommand } = await import('../data');
    await dataCommand(['export', '--id', 'sym-export-001', '--format', 'csv']);

    const logCalls = consoleLogSpy.mock.calls.map(([arg]: [unknown]) => String(arg));
    const csvOutput = logCalls.find((c: string) =>
      c.includes('timestamp,open,high,low,close,volume'),
    );
    expect(csvOutput).toBeDefined();
    expect(csvOutput).toContain('42000');
  });

  test('writes JSON data to file with --output', async () => {
    fetchMock = mock((url: string, options?: RequestInit) => {
      const method = options?.method ?? 'GET';
      if (
        url.includes('/api/v1/symbols/sym-export-001') &&
        method === 'GET' &&
        !url.includes('/data')
      ) {
        return Promise.resolve(jsonResponse({ data: sampleSymbol }));
      }
      if (url.includes('/api/v1/symbols/sym-export-001/data') && method === 'GET') {
        return Promise.resolve(jsonResponse({ data: sampleOhlcData }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const outputPath = join(tempDir, 'export.json');
    const { dataCommand } = await import('../data');
    await dataCommand(['export', '--id', 'sym-export-001', '--output', outputPath]);

    expect(existsSync(outputPath)).toBe(true);
    const content = JSON.parse(readFileSync(outputPath, 'utf-8')) as OhlcDataPoint[];
    expect(content).toHaveLength(3);
    expect(content[0].timestamp).toBe('2025-01-01 00:00:00');
  });

  test('writes CSV data to file with --output and --format csv', async () => {
    fetchMock = mock((url: string, options?: RequestInit) => {
      const method = options?.method ?? 'GET';
      if (
        url.includes('/api/v1/symbols/sym-export-001') &&
        method === 'GET' &&
        !url.includes('/data')
      ) {
        return Promise.resolve(jsonResponse({ data: sampleSymbol }));
      }
      if (url.includes('/api/v1/symbols/sym-export-001/data') && method === 'GET') {
        return Promise.resolve(jsonResponse({ data: sampleOhlcData }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const outputPath = join(tempDir, 'export.csv');
    const { dataCommand } = await import('../data');
    await dataCommand([
      'export',
      '--id',
      'sym-export-001',
      '--format',
      'csv',
      '--output',
      outputPath,
    ]);

    expect(existsSync(outputPath)).toBe(true);
    const content = readFileSync(outputPath, 'utf-8');
    expect(content).toContain('timestamp,open,high,low,close,volume');
    expect(content).toContain('42000');
  });

  test('exits with error when --id is missing', async () => {
    const { dataCommand } = await import('../data');

    try {
      await dataCommand(['export']);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
    }
  });

  test('exits with error on invalid --format', async () => {
    const { dataCommand } = await import('../data');

    try {
      await dataCommand(['export', '--id', 'sym-001', '--format', 'xml']);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
    }
  });

  test('shows actionable 404 error when symbol not found', async () => {
    fetchMock = mock((url: string, options?: RequestInit) => {
      const method = options?.method ?? 'GET';
      if (url.includes('/api/v1/symbols/nonexistent') && method === 'GET') {
        return Promise.resolve(jsonResponse({ error: { message: 'Not Found' } }, 404));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { dataCommand } = await import('../data');

    try {
      await dataCommand(['export', '--id', 'nonexistent']);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
      const rendered = consoleErrorSpy.mock.calls.map(([arg]: [unknown]) => String(arg)).join(' ');
      expect(rendered).toContain('not found');
    }
  });

  test('fetches data from file_url when symbol has one', async () => {
    const csvData =
      'timestamp,open,high,low,close,volume\n2025-01-01 00:00:00,42000,42500,41800,42200,1500';
    const symbolWithUrl = { ...sampleSymbol, file_url: 'https://storage.example.com/data.csv' };

    fetchMock = mock((url: string, options?: RequestInit) => {
      const method = options?.method ?? 'GET';
      // getSymbol call
      if (
        url.includes('/api/v1/symbols/sym-export-001') &&
        method === 'GET' &&
        !url.includes('/data')
      ) {
        return Promise.resolve(jsonResponse({ data: symbolWithUrl }));
      }
      // file_url fetch
      if (url === 'https://storage.example.com/data.csv') {
        return Promise.resolve(
          new Response(csvData, { status: 200, headers: { 'Content-Type': 'text/csv' } }),
        );
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { dataCommand } = await import('../data');
    await dataCommand(['export', '--id', 'sym-export-001']);

    const logCalls = consoleLogSpy.mock.calls.map(([arg]: [unknown]) => String(arg));
    const jsonOutput = logCalls.find((c: string) => c.includes('"timestamp"'));
    expect(jsonOutput).toBeDefined();

    const parsed = JSON.parse(jsonOutput!) as OhlcDataPoint[];
    expect(parsed).toHaveLength(1);
    expect(parsed[0].open).toBe(42000);
  });
});
