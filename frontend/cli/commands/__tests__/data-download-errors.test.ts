import { afterEach, beforeEach, describe, expect, mock, spyOn, test } from 'bun:test';

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

describe('data download improved 404 errors', () => {
  let consoleLogSpy: ReturnType<typeof spyOn>;
  let consoleErrorSpy: ReturnType<typeof spyOn>;
  let stdoutWriteSpy: ReturnType<typeof spyOn>;
  let fetchMock: ReturnType<typeof mock>;

  beforeEach(() => {
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
  });

  test('shows actionable error when Binance returns 400 for invalid symbol', async () => {
    fetchMock = mock((url: string) => {
      if (url.includes('binance.com')) {
        return Promise.resolve(
          new Response(JSON.stringify({ code: -1121, msg: 'Invalid symbol.' }), {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { dataCommand } = await import('../data');

    try {
      await dataCommand([
        'download',
        '--symbol',
        'INVALIDPAIR',
        '--start',
        '2025-01-01',
        '--end',
        '2025-06-01',
      ]);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
      const rendered = consoleErrorSpy.mock.calls.map(([arg]: [unknown]) => String(arg)).join(' ');
      expect(rendered).toContain('not found on Binance');
      expect(rendered).toContain('INVALIDPAIR');
    }
  });

  test('shows actionable error when Binance returns 404', async () => {
    fetchMock = mock((url: string) => {
      if (url.includes('binance.com')) {
        return Promise.resolve(new Response('Not Found', { status: 404 }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { dataCommand } = await import('../data');

    try {
      await dataCommand([
        'download',
        '--symbol',
        'BTCUSDT',
        '--start',
        '2025-01-01',
        '--end',
        '2025-06-01',
      ]);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
      const rendered = consoleErrorSpy.mock.calls.map(([arg]: [unknown]) => String(arg)).join(' ');
      expect(rendered).toContain('Binance');
      expect(rendered).toContain('BTCUSDT');
    }
  });

  test('shows specific 404 error for Lona upload failure', async () => {
    fetchMock = mock((url: string, options?: RequestInit) => {
      const method = options?.method ?? 'GET';
      // Binance succeeds with empty data
      if (url.includes('binance.com')) {
        return Promise.resolve(
          new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      // Upload to Lona fails with 404
      if (url.includes('/api/v1/symbols') && method === 'POST') {
        return Promise.resolve(jsonResponse({ error: { message: 'Not Found' } }, 404));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { dataCommand } = await import('../data');

    try {
      await dataCommand([
        'download',
        '--symbol',
        'BTCUSDT',
        '--start',
        '2025-01-01',
        '--end',
        '2025-06-01',
      ]);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
      const rendered = consoleErrorSpy.mock.calls.map(([arg]: [unknown]) => String(arg)).join(' ');
      // Non-Binance 404: passes through the Lona error message directly
      expect(rendered).toContain('404');
    }
  });

  test('download 404 error message preserves Lona error context', async () => {
    fetchMock = mock((url: string, options?: RequestInit) => {
      const method = options?.method ?? 'GET';
      // Binance succeeds
      if (url.includes('binance.com')) {
        return Promise.resolve(
          new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        );
      }
      // Upload succeeds
      if (url.includes('/api/v1/symbols') && method === 'POST') {
        return Promise.resolve(jsonResponse({ data: { id: 'sym-new' } }));
      }
      // getSymbol after upload returns 404
      if (url.includes('/api/v1/symbols/sym-new') && method === 'GET') {
        return Promise.resolve(jsonResponse({ detail: 'Not Found' }, 404));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { dataCommand } = await import('../data');

    try {
      await dataCommand([
        'download',
        '--symbol',
        'BTCUSDT',
        '--start',
        '2025-01-01',
        '--end',
        '2025-06-01',
      ]);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
      const rendered = consoleErrorSpy.mock.calls.map(([arg]: [unknown]) => String(arg)).join(' ');
      // Non-Binance Lona 404: preserves the original error (not Binance hint)
      expect(rendered).toContain('Not Found');
    }
  });
});
