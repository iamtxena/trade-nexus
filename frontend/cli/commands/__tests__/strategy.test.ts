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

describe('strategy command backtest flags', () => {
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

  function mockSuccessfulBacktestFetch(): Array<{ url: string; options: RequestInit }> {
    const calls: Array<{ url: string; options: RequestInit }> = [];
    const fetchMock = mock((url: string, options?: RequestInit) => {
      calls.push({ url, options: options ?? {} });

      if (url.includes('/api/v1/runner/run') && options?.method === 'POST') {
        return Promise.resolve(jsonResponse({ data: { report_id: 'report-001' } }));
      }
      if (url.includes('/api/v1/reports/report-001/status') && (options?.method ?? 'GET') === 'GET') {
        return Promise.resolve(jsonResponse({ data: { status: 'COMPLETED' } }));
      }
      if (
        url.includes('/api/v1/reports/report-001') &&
        !url.includes('/status') &&
        (options?.method ?? 'GET') === 'GET'
      ) {
        return Promise.resolve(
          jsonResponse({
            data: {
              id: 'report-001',
              strategy_id: 'strat-test',
              total_stats: { sharpe_ratio: 1.2 },
            },
          }),
        );
      }

      return Promise.resolve(jsonResponse({ data: {} }));
    });

    globalThis.fetch = fetchMock as unknown as typeof fetch;
    return calls;
  }

  test('accepts --strategy-id and --symbol-id for backtest', async () => {
    const calls = mockSuccessfulBacktestFetch();
    const { strategyCommand } = await import('../strategy');

    await strategyCommand([
      'backtest',
      '--strategy-id',
      'strat-new',
      '--symbol-id',
      'sym-1, sym-2',
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
    expect(body.strategy_id).toBe('strat-new');
    expect(body.data_ids).toEqual(['sym-1', 'sym-2']);
  });

  test('accepts legacy --id and --data aliases for backtest', async () => {
    const calls = mockSuccessfulBacktestFetch();
    const { strategyCommand } = await import('../strategy');

    await strategyCommand([
      'backtest',
      '--id',
      'strat-legacy',
      '--data',
      'sym-legacy',
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
    expect(body.strategy_id).toBe('strat-legacy');
    expect(body.data_ids).toEqual(['sym-legacy']);

    const logOutput = consoleLogSpy.mock.calls.map(([line]) => String(line)).join('\n');
    expect(logOutput).toContain('Using legacy --id for backtest strategy. Prefer --strategy-id.');
    expect(logOutput).toContain('Using legacy --data for backtest symbol. Prefer --symbol-id.');
  });

  test('errors when required backtest flags are missing', async () => {
    const { strategyCommand } = await import('../strategy');

    await expect(
      strategyCommand([
        'backtest',
        '--strategy-id',
        'strat-missing-symbol',
        '--start',
        '2025-01-01',
        '--end',
        '2025-02-01',
      ]),
    ).rejects.toThrow('process.exit(1)');

    const errorOutput = consoleErrorSpy.mock.calls.map(([line]) => String(line)).join('\n');
    expect(errorOutput).toContain(
      'Required: --strategy-id <strategyId> (alias: --id) --symbol-id <dataId> (alias: --data) --start YYYY-MM-DD --end YYYY-MM-DD',
    );
  });

  test('errors on conflicting strategy flags', async () => {
    const { strategyCommand } = await import('../strategy');

    await expect(
      strategyCommand([
        'backtest',
        '--strategy-id',
        'strat-primary',
        '--id',
        'strat-legacy',
        '--symbol-id',
        'sym-1',
        '--start',
        '2025-01-01',
        '--end',
        '2025-02-01',
      ]),
    ).rejects.toThrow('process.exit(1)');

    const errorOutput = consoleErrorSpy.mock.calls.map(([line]) => String(line)).join('\n');
    expect(errorOutput).toContain('Conflicting values for --strategy-id and --id');
  });

  test('errors on conflicting symbol flags', async () => {
    const { strategyCommand } = await import('../strategy');

    await expect(
      strategyCommand([
        'backtest',
        '--strategy-id',
        'strat-1',
        '--symbol-id',
        'sym-primary',
        '--data',
        'sym-legacy',
        '--start',
        '2025-01-01',
        '--end',
        '2025-02-01',
      ]),
    ).rejects.toThrow('process.exit(1)');

    const errorOutput = consoleErrorSpy.mock.calls.map(([line]) => String(line)).join('\n');
    expect(errorOutput).toContain('Conflicting values for --symbol-id and --data');
  });
});
