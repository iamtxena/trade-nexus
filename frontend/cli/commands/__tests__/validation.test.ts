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
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('validation command', () => {
  let consoleLogSpy: ReturnType<typeof spyOn>;
  let consoleErrorSpy: ReturnType<typeof spyOn>;
  let stdoutWriteSpy: ReturnType<typeof spyOn>;
  let fetchMock: ReturnType<typeof mock>;
  let tempCliHome: string;

  beforeEach(() => {
    tempCliHome = mkdtempSync(join(tmpdir(), 'nexus-validation-cli-'));

    process.env = {
      ...originalEnv,
      ML_BACKEND_URL: 'https://platform.example.com',
      LONA_AGENT_TOKEN: 'test-platform-token',
      LONA_AGENT_ID: 'test-platform-user',
      NEXUS_CLI_HOME: tempCliHome,
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
    rmSync(tempCliHome, { recursive: true, force: true });
  });

  test('create submits platform payload and optional html/pdf render triggers', async () => {
    const callLog: Array<{ url: string; options: RequestInit }> = [];

    fetchMock = mock((url: string, options?: RequestInit) => {
      callLog.push({ url, options: options ?? {} });

      if (url.endsWith('/v2/validation-runs') && options?.method === 'POST') {
        return Promise.resolve(
          jsonResponse({
            requestId: 'req-v-create-001',
            run: {
              id: 'valrun-0001',
              status: 'queued',
              profile: 'STANDARD',
              schemaVersion: 'validation-run.v1',
              finalDecision: 'pending',
              createdAt: '2026-02-19T12:00:00Z',
              updatedAt: '2026-02-19T12:00:00Z',
            },
          }),
        );
      }

      if (
        url.includes('/v2/validation-runs/valrun-0001/render') &&
        options?.method === 'POST' &&
        typeof options.body === 'string'
      ) {
        const parsed = JSON.parse(options.body) as { format: 'html' | 'pdf' };
        return Promise.resolve(
          jsonResponse({
            requestId: `req-v-render-${parsed.format}`,
            render: {
              runId: 'valrun-0001',
              format: parsed.format,
              status: 'queued',
              artifactRef: null,
            },
          }),
        );
      }

      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { validationCommand } = await import('../validation');
    await validationCommand([
      'create',
      '--strategy-id',
      'strat-001',
      '--requested-indicators',
      'zigzag,ema',
      '--dataset-ids',
      'dataset-1,dataset-2',
      '--backtest-report-ref',
      'blob://validation/candidate/backtest-report.json',
      '--profile',
      'STANDARD',
      '--render',
      'html,pdf',
      '--request-id',
      'req-v-create-001',
      '--idempotency-key',
      'idem-v-create-001',
    ]);

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(callLog[0].url).toBe('https://platform.example.com/v2/validation-runs');
    expect(callLog[0].url.includes('gateway.lona.agency')).toBe(false);
    expect(callLog[0].url.includes('live.lona.agency')).toBe(false);

    const createBody = JSON.parse(String(callLog[0].options.body)) as Record<string, unknown>;
    expect(createBody.strategyId).toBe('strat-001');
    expect(createBody.requestedIndicators).toEqual(['zigzag', 'ema']);
    expect(createBody.datasetIds).toEqual(['dataset-1', 'dataset-2']);
    expect((createBody.policy as Record<string, unknown>).profile).toBe('STANDARD');

    const createHeaders = callLog[0].options.headers as Record<string, string>;
    expect(createHeaders['X-API-Key']).toBe('test-platform-token');
    expect(createHeaders['Idempotency-Key']).toBe('idem-v-create-001');

    expect(callLog[1].url).toContain('/v2/validation-runs/valrun-0001/render');
    expect(callLog[2].url).toContain('/v2/validation-runs/valrun-0001/render');

    const historyPath = join(tempCliHome, 'validation-history.json');
    expect(existsSync(historyPath)).toBe(true);
    const history = JSON.parse(readFileSync(historyPath, 'utf-8')) as {
      runs: Array<{ runId: string; status?: string }>;
    };
    const runEntry = history.runs.find((entry) => entry.runId === 'valrun-0001');
    expect(runEntry).toBeDefined();
    expect(runEntry?.status).toBe('queued');
  });

  test('list uses local history and does not call platform API', async () => {
    fetchMock = mock((url: string, options?: RequestInit) => {
      if (url.endsWith('/v2/validation-runs') && options?.method === 'POST') {
        return Promise.resolve(
          jsonResponse({
            requestId: 'req-v-create-002',
            run: {
              id: 'valrun-0002',
              status: 'queued',
              profile: 'STANDARD',
              schemaVersion: 'validation-run.v1',
              finalDecision: 'pending',
              createdAt: '2026-02-19T12:00:00Z',
              updatedAt: '2026-02-19T12:00:00Z',
            },
          }),
        );
      }
      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { validationCommand } = await import('../validation');
    await validationCommand([
      'create',
      '--strategy-id',
      'strat-002',
      '--requested-indicators',
      'ema',
      '--dataset-ids',
      'dataset-1',
      '--backtest-report-ref',
      'blob://validation/candidate/backtest-report.json',
    ]);
    const callCountAfterCreate = fetchMock.mock.calls.length;

    await validationCommand(['list', '--kind', 'runs', '--limit', '5']);

    expect(fetchMock.mock.calls.length).toBe(callCountAfterCreate);
  });

  test('get --artifact calls validation artifact endpoint', async () => {
    fetchMock = mock((url: string, options?: RequestInit) => {
      expect(options?.method).toBe('GET');
      return Promise.resolve(
        jsonResponse({
          requestId: 'req-v-artifact-001',
          artifactType: 'validation_run',
          artifact: {
            runId: 'valrun-0100',
            schemaVersion: 'validation-run.v1',
          },
        }),
      );
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { validationCommand } = await import('../validation');
    await validationCommand(['get', '--id', 'valrun-0100', '--artifact']);

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://platform.example.com/v2/validation-runs/valrun-0100/artifact');
  });

  test('review submits decision and optional render trigger via platform API', async () => {
    const callLog: Array<{ url: string; options: RequestInit }> = [];

    fetchMock = mock((url: string, options?: RequestInit) => {
      callLog.push({ url, options: options ?? {} });

      if (url.includes('/v2/validation-runs/valrun-0003/review') && options?.method === 'POST') {
        return Promise.resolve(
          jsonResponse({
            requestId: 'req-v-review-001',
            runId: 'valrun-0003',
            reviewAccepted: true,
          }),
        );
      }

      if (url.includes('/v2/validation-runs/valrun-0003/render') && options?.method === 'POST') {
        return Promise.resolve(
          jsonResponse({
            requestId: 'req-v-review-render-001',
            render: {
              runId: 'valrun-0003',
              format: 'html',
              status: 'queued',
              artifactRef: null,
            },
          }),
        );
      }

      return Promise.resolve(jsonResponse({}));
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { validationCommand } = await import('../validation');
    await validationCommand([
      'review',
      '--run-id',
      'valrun-0003',
      '--reviewer',
      'trader',
      '--decision',
      'pass',
      '--summary',
      'Looks good',
      '--comments',
      'approved,ship-it',
      '--render',
      'html',
      '--request-id',
      'req-v-review-001',
      '--idempotency-key',
      'idem-v-review-001',
    ]);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(callLog[0].url).toBe(
      'https://platform.example.com/v2/validation-runs/valrun-0003/review',
    );
    expect(callLog[1].url).toBe(
      'https://platform.example.com/v2/validation-runs/valrun-0003/render',
    );

    const reviewBody = JSON.parse(String(callLog[0].options.body)) as Record<string, unknown>;
    expect(reviewBody.reviewerType).toBe('trader');
    expect(reviewBody.decision).toBe('pass');
    expect(reviewBody.summary).toBe('Looks good');
    expect(reviewBody.comments).toEqual(['approved', 'ship-it']);

    const reviewHeaders = callLog[0].options.headers as Record<string, string>;
    expect(reviewHeaders['Idempotency-Key']).toBe('idem-v-review-001');

    const renderHeaders = callLog[1].options.headers as Record<string, string>;
    expect(renderHeaders['Idempotency-Key']).toBe('idem-v-review-001-render-html-0');
    expect(renderHeaders['X-Request-Id']).toBe('req-v-review-001-render-html-0');
  });

  test('render supports html,pdf fan-out with distinct idempotency keys', async () => {
    const callLog: Array<{ url: string; options: RequestInit }> = [];

    fetchMock = mock((url: string, options?: RequestInit) => {
      callLog.push({ url, options: options ?? {} });
      const body =
        typeof options?.body === 'string'
          ? (JSON.parse(options.body) as { format: 'html' | 'pdf' })
          : { format: 'html' as const };

      return Promise.resolve(
        jsonResponse({
          requestId: `req-v-render-${body.format}`,
          render: {
            runId: 'valrun-0099',
            format: body.format,
            status: 'queued',
            artifactRef: null,
          },
        }),
      );
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { validationCommand } = await import('../validation');
    await validationCommand([
      'render',
      '--run-id',
      'valrun-0099',
      '--format',
      'html,pdf',
      '--request-id',
      'req-v-render-0099',
      '--idempotency-key',
      'idem-v-render-0099',
    ]);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const firstHeaders = callLog[0].options.headers as Record<string, string>;
    const secondHeaders = callLog[1].options.headers as Record<string, string>;
    expect(firstHeaders['Idempotency-Key']).toBe('idem-v-render-0099-render-html-0');
    expect(secondHeaders['Idempotency-Key']).toBe('idem-v-render-0099-render-pdf-1');

    const firstBody = JSON.parse(String(callLog[0].options.body)) as { format: string };
    const secondBody = JSON.parse(String(callLog[1].options.body)) as { format: string };
    expect(firstBody.format).toBe('html');
    expect(secondBody.format).toBe('pdf');
  });

  test('replay submits baseline/candidate payload and records local replay history', async () => {
    fetchMock = mock((url: string, options?: RequestInit) => {
      expect(url).toBe('https://platform.example.com/v2/validation-regressions/replay');
      const body = JSON.parse(String(options?.body)) as {
        baselineId: string;
        candidateRunId: string;
        policyOverrides: { forceStrict: boolean };
      };
      expect(body.baselineId).toBe('valbase-001');
      expect(body.candidateRunId).toBe('valrun-0010');
      expect(body.policyOverrides.forceStrict).toBe(true);
      return Promise.resolve(
        jsonResponse({
          requestId: 'req-v-replay-001',
          replay: {
            id: 'valreplay-001',
            baselineId: 'valbase-001',
            candidateRunId: 'valrun-0010',
            status: 'queued',
            decision: 'unknown',
            summary: 'Replay accepted for execution.',
          },
        }),
      );
    });
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { validationCommand } = await import('../validation');
    await validationCommand([
      'replay',
      '--baseline-id',
      'valbase-001',
      '--candidate-run-id',
      'valrun-0010',
      '--policy-overrides',
      '{"forceStrict":true}',
    ]);

    const historyPath = join(tempCliHome, 'validation-history.json');
    const history = JSON.parse(readFileSync(historyPath, 'utf-8')) as {
      replays: Array<{ replayId: string; baselineId: string; candidateRunId: string }>;
    };
    expect(
      history.replays.some(
        (entry) =>
          entry.replayId === 'valreplay-001' &&
          entry.baselineId === 'valbase-001' &&
          entry.candidateRunId === 'valrun-0010',
      ),
    ).toBe(true);
  });

  test('replay exits when --policy-overrides is invalid JSON', async () => {
    const { validationCommand } = await import('../validation');

    try {
      await validationCommand([
        'replay',
        '--baseline-id',
        'valbase-001',
        '--candidate-run-id',
        'valrun-0010',
        '--policy-overrides',
        '{not-json}',
      ]);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
    }
  });

  test('replay preserves explicit non-object override error message', async () => {
    const { validationCommand } = await import('../validation');

    try {
      await validationCommand([
        'replay',
        '--baseline-id',
        'valbase-001',
        '--candidate-run-id',
        'valrun-0010',
        '--policy-overrides',
        '[]',
      ]);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
      const rendered = String(consoleErrorSpy.mock.calls.at(-1)?.[0] ?? '');
      expect(rendered.includes('--policy-overrides must be a JSON object')).toBe(true);
    }
  });

  test('exits on missing required review args', async () => {
    const { validationCommand } = await import('../validation');

    try {
      await validationCommand(['review', '--reviewer', 'trader', '--decision', 'pass']);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
    }
  });

  test('exits on platform API error envelope', async () => {
    fetchMock = mock((_url: string, _options?: RequestInit) =>
      Promise.resolve(
        jsonResponse(
          {
            requestId: 'req-v-err-001',
            error: {
              code: 'VALIDATION_STATE_INVALID',
              message: 'Validation run references unknown strategyId.',
            },
          },
          400,
        ),
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { validationCommand } = await import('../validation');

    try {
      await validationCommand([
        'create',
        '--strategy-id',
        'strat-bad',
        '--requested-indicators',
        'ema',
        '--dataset-ids',
        'dataset-1',
        '--backtest-report-ref',
        'blob://validation/candidate/backtest-report.json',
      ]);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
      expect(consoleErrorSpy).toHaveBeenCalled();
    }
  });

  test('review exits on invalid-state 409 envelope', async () => {
    fetchMock = mock((_url: string, _options?: RequestInit) =>
      Promise.resolve(
        jsonResponse(
          {
            requestId: 'req-v-review-conflict-001',
            error: {
              code: 'VALIDATION_STATE_CONFLICT',
              message: 'Review not allowed when run is queued.',
            },
          },
          409,
        ),
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { validationCommand } = await import('../validation');

    try {
      await validationCommand([
        'review',
        '--run-id',
        'valrun-0003',
        '--reviewer',
        'trader',
        '--decision',
        'pass',
      ]);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
      const rendered = String(consoleErrorSpy.mock.calls.at(-1)?.[0] ?? '');
      expect(
        rendered.includes(
          'Platform API error 409 (VALIDATION_STATE_CONFLICT): Review not allowed when run is queued. [requestId=req-v-review-conflict-001]',
        ),
      ).toBe(true);
    }
  });

  test('render exits on invalid-state 409 envelope', async () => {
    fetchMock = mock((_url: string, _options?: RequestInit) =>
      Promise.resolve(
        jsonResponse(
          {
            requestId: 'req-v-render-conflict-001',
            error: {
              code: 'VALIDATION_STATE_CONFLICT',
              message: 'Render cannot be requested before review is finalized.',
            },
          },
          409,
        ),
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const { validationCommand } = await import('../validation');

    try {
      await validationCommand(['render', '--run-id', 'valrun-0003', '--format', 'html']);
      expect(true).toBe(false);
    } catch (error) {
      expect((error as Error).message).toBe('process.exit(1)');
      const rendered = String(consoleErrorSpy.mock.calls.at(-1)?.[0] ?? '');
      expect(
        rendered.includes(
          'Platform API error 409 (VALIDATION_STATE_CONFLICT): Render cannot be requested before review is finalized. [requestId=req-v-render-conflict-001]',
        ),
      ).toBe(true);
    }
  });
});
