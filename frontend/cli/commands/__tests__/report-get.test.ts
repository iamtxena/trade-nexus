import { afterEach, beforeEach, describe, expect, mock, spyOn, test } from 'bun:test';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const originalFetch = globalThis.fetch;
const originalExit = process.exit;
const originalEnv = { ...process.env };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    headers: { 'Content-Type': 'application/json' },
  });
}

const sampleReport = {
  id: 'rpt-001',
  strategy_id: 'strat-001',
  status: 'COMPLETED',
  name: 'BTC Momentum Backtest',
  description: 'Backtest of BTC momentum strategy',
  created_at: '2025-01-15T10:30:00Z',
  updated_at: '2025-01-15T11:00:00Z',
  total_stats: {
    total_return: 0.1523,
    sharpe_ratio: 1.45,
    max_drawdown: -0.0832,
    total_trades: 42,
    win_rate: 0.62,
  },
  error: null,
};

const sampleFullReport = {
  ...sampleReport,
  backtest_timeline: [
    { date: '2025-01-01', equity: 10000, drawdown: 0 },
    { date: '2025-01-02', equity: 10150, drawdown: 0 },
    { date: '2025-01-03', equity: 10080, drawdown: -0.007 },
  ],
  parameters: { initial_cash: 10000 },
};

describe('report get command', () => {
  let consoleLogSpy: ReturnType<typeof spyOn>;
  let consoleErrorSpy: ReturnType<typeof spyOn>;
  let stdoutWriteSpy: ReturnType<typeof spyOn>;
  let fetchMock: ReturnType<typeof mock>;
  let tempDir: string;

  beforeEach(() => {
    tempDir = mkdtempSync(join(tmpdir(), 'nexus-report-get-'));

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

  test('prints summary stats by default', async () => {
    fetchMock = mock((url: string) => {
      if (
        url.includes('/api/v1/reports/rpt-001') &&
        !url.includes('/full') &&
        !url.includes('/status')
      ) {
        return Promise.resolve(jsonResponse({ data: sampleReport }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { reportCommand } = await import('../report');
    await reportCommand(['get', '--id', 'rpt-001']);

    const logCalls = consoleLogSpy.mock.calls.map(([arg]: [unknown]) => String(arg));
    const allOutput = logCalls.join('\n');
    expect(allOutput).toContain('rpt-001');
    expect(allOutput).toContain('BTC Momentum Backtest');
  });

  test('outputs full report with --full', async () => {
    fetchMock = mock((url: string) => {
      if (url.includes('/api/v1/reports/rpt-001/full')) {
        return Promise.resolve(jsonResponse({ data: sampleFullReport }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { reportCommand } = await import('../report');
    await reportCommand(['get', '--id', 'rpt-001', '--full']);

    const logCalls = consoleLogSpy.mock.calls.map(([arg]: [unknown]) => String(arg));
    const jsonOutput = logCalls.find((c: string) => c.includes('backtest_timeline'));
    expect(jsonOutput).toBeDefined();

    const parsed = JSON.parse(jsonOutput!) as typeof sampleFullReport;
    expect(parsed.backtest_timeline).toHaveLength(3);
  });

  test('outputs only timeline with --timeline', async () => {
    fetchMock = mock((url: string) => {
      if (url.includes('/api/v1/reports/rpt-001/full')) {
        return Promise.resolve(jsonResponse({ data: sampleFullReport }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { reportCommand } = await import('../report');
    await reportCommand(['get', '--id', 'rpt-001', '--timeline']);

    const logCalls = consoleLogSpy.mock.calls.map(([arg]: [unknown]) => String(arg));
    const jsonOutput = logCalls.find((c: string) => c.includes('"date"'));
    expect(jsonOutput).toBeDefined();

    const parsed = JSON.parse(jsonOutput!) as Array<{ date: string }>;
    expect(parsed).toHaveLength(3);
    expect(parsed[0].date).toBe('2025-01-01');
  });

  test('writes report to file with --output', async () => {
    fetchMock = mock((url: string) => {
      if (
        url.includes('/api/v1/reports/rpt-001') &&
        !url.includes('/full') &&
        !url.includes('/status')
      ) {
        return Promise.resolve(jsonResponse({ data: sampleReport }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const outputPath = join(tempDir, 'report.json');
    const { reportCommand } = await import('../report');
    await reportCommand(['get', '--id', 'rpt-001', '--output', outputPath]);

    expect(existsSync(outputPath)).toBe(true);
    const content = JSON.parse(readFileSync(outputPath, 'utf-8')) as typeof sampleReport;
    expect(content.id).toBe('rpt-001');
    expect(content.total_stats?.total_return).toBe(0.1523);
  });

  test('writes full report to file with --full --output', async () => {
    fetchMock = mock((url: string) => {
      if (url.includes('/api/v1/reports/rpt-001/full')) {
        return Promise.resolve(jsonResponse({ data: sampleFullReport }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const outputPath = join(tempDir, 'full-report.json');
    const { reportCommand } = await import('../report');
    await reportCommand(['get', '--id', 'rpt-001', '--full', '--output', outputPath]);

    expect(existsSync(outputPath)).toBe(true);
    const content = JSON.parse(readFileSync(outputPath, 'utf-8')) as typeof sampleFullReport;
    expect(content.backtest_timeline).toHaveLength(3);
  });

  test('writes timeline to file with --timeline --output', async () => {
    fetchMock = mock((url: string) => {
      if (url.includes('/api/v1/reports/rpt-001/full')) {
        return Promise.resolve(jsonResponse({ data: sampleFullReport }));
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const outputPath = join(tempDir, 'timeline.json');
    const { reportCommand } = await import('../report');
    await reportCommand(['get', '--id', 'rpt-001', '--timeline', '--output', outputPath]);

    expect(existsSync(outputPath)).toBe(true);
    const content = JSON.parse(readFileSync(outputPath, 'utf-8')) as Array<{ date: string }>;
    expect(content).toHaveLength(3);
  });

  test('exits with error when --id is missing', async () => {
    const { reportCommand } = await import('../report');

    try {
      await reportCommand(['get']);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
    }
  });

  test('exits with error on API failure', async () => {
    fetchMock = mock((_url: string) => {
      return Promise.resolve(jsonResponse({ error: { message: 'Report not found' } }, 404));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { reportCommand } = await import('../report');

    try {
      await reportCommand(['get', '--id', 'rpt-nonexistent']);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
    }
  });
});
