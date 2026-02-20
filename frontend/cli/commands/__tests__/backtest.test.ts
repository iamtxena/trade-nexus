import { afterEach, beforeEach, describe, expect, mock, spyOn, test } from 'bun:test';

const originalFetch = globalThis.fetch;
const originalExit = process.exit;
const originalEnv = { ...process.env };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('backtest command alias', () => {
  let consoleLogSpy: ReturnType<typeof spyOn>;
  let consoleErrorSpy: ReturnType<typeof spyOn>;
  let stdoutWriteSpy: ReturnType<typeof spyOn>;

  beforeEach(() => {
    process.env = {
      ...originalEnv,
      LONA_AGENT_TOKEN: 'test-token',
      LONA_AGENT_ID: 'test-agent',
      LONA_GATEWAY_URL: 'https://gateway.example.com',
    };

    consoleLogSpy = spyOn(console, 'log').mockImplementation(() => {});
    consoleErrorSpy = spyOn(console, 'error').mockImplementation(() => {});
    stdoutWriteSpy = spyOn(process.stdout, 'write').mockImplementation(() => true);

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

  test('runs backtest through top-level alias command', async () => {
    const calls: Array<{ url: string; options: RequestInit }> = [];
    const fetchMock = mock((url: string, options?: RequestInit) => {
      calls.push({ url, options: options ?? {} });

      if (url.includes('/api/v1/runner/run') && options?.method === 'POST') {
        return Promise.resolve(jsonResponse({ data: { report_id: 'report-002' } }));
      }
      if (url.includes('/api/v1/reports/report-002/status') && (options?.method ?? 'GET') === 'GET') {
        return Promise.resolve(jsonResponse({ data: { status: 'COMPLETED' } }));
      }
      if (
        url.includes('/api/v1/reports/report-002') &&
        !url.includes('/status') &&
        (options?.method ?? 'GET') === 'GET'
      ) {
        return Promise.resolve(
          jsonResponse({
            data: {
              id: 'report-002',
              strategy_id: 'strat-alias',
              total_stats: { sharpe_ratio: 0.9 },
            },
          }),
        );
      }

      return Promise.resolve(jsonResponse({ data: {} }));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { backtestCommand } = await import('../backtest');
    await backtestCommand([
      '--strategy-id',
      'strat-alias',
      '--symbol-id',
      'sym-alias',
      '--start',
      '2025-01-01',
      '--end',
      '2025-02-01',
    ]);

    const runCall = calls.find((call) => call.url.includes('/api/v1/runner/run'));
    expect(runCall).toBeDefined();
    const body = JSON.parse(String(runCall?.options.body)) as {
      strategy_id: string;
      data_ids: string[];
    };
    expect(body.strategy_id).toBe('strat-alias');
    expect(body.data_ids).toEqual(['sym-alias']);
  });

  test('prints required flags error text from alias command', async () => {
    const { backtestCommand } = await import('../backtest');

    await expect(backtestCommand([])).rejects.toThrow('process.exit(1)');
    const errorOutput = consoleErrorSpy.mock.calls.map(([line]) => String(line)).join('\n');
    expect(errorOutput).toContain(
      'Required: --strategy-id <strategyId> (alias: --id) --symbol-id <dataId> (alias: --data) --start YYYY-MM-DD --end YYYY-MM-DD',
    );
  });
});
