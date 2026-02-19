import { afterEach, beforeEach, describe, expect, mock, test } from 'bun:test';

import { PlatformApiError, getPlatformApiClient } from '../platform-api';

const originalFetch = globalThis.fetch;
const originalEnv = { ...process.env };

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('platform api client', () => {
  beforeEach(() => {
    process.env = {
      ...originalEnv,
      ML_BACKEND_URL: 'https://platform.example.com',
      LONA_AGENT_TOKEN: 'test-platform-token',
      LONA_AGENT_ID: 'test-platform-user',
    };
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    process.env = { ...originalEnv };
  });

  test('targets platform validation endpoints with boundary headers', async () => {
    const fetchMock = mock((_url: string, _options?: RequestInit) =>
      Promise.resolve(
        jsonResponse({
          requestId: 'req-v-get-001',
          run: {
            id: 'valrun-0001',
            status: 'completed',
            profile: 'STANDARD',
            schemaVersion: 'validation-run.v1',
            finalDecision: 'pass',
            createdAt: '2026-02-19T00:00:00Z',
            updatedAt: '2026-02-19T00:00:00Z',
          },
        }),
      ),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const client = getPlatformApiClient();
    await client.getValidationRun('valrun-0001', { requestId: 'req-v-get-001' });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('https://platform.example.com/v2/validation-runs/valrun-0001');
    expect(url.includes('gateway.lona.agency')).toBe(false);
    expect(url.includes('live.lona.agency')).toBe(false);

    const headers = options.headers as Record<string, string>;
    expect(headers['X-Request-Id']).toBe('req-v-get-001');
    expect(headers['X-API-Key']).toBe('test-platform-token');
    expect(headers['X-User-Id']).toBe('test-platform-user');
    expect(headers['X-Tenant-Id']).toBe('tenant-local');
  });

  test('raises structured PlatformApiError for error envelopes', async () => {
    const fetchMock = mock((_url: string, _options?: RequestInit) =>
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

    const client = getPlatformApiClient();

    try {
      await client.getValidationRun('valrun-missing');
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(PlatformApiError);
      const platformError = error as PlatformApiError;
      expect(platformError.statusCode).toBe(400);
      expect(platformError.code).toBe('VALIDATION_STATE_INVALID');
      expect(platformError.requestId).toBe('req-v-err-001');
      expect(platformError.message).toContain('VALIDATION_STATE_INVALID');
    }
  });

  test('wraps fetch failures as PlatformApiError', async () => {
    const fetchMock = mock((_url: string, _options?: RequestInit) =>
      Promise.reject(new Error('network down')),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    const client = getPlatformApiClient();

    try {
      await client.getValidationRun('valrun-timeout');
      expect(true).toBe(false);
    } catch (error) {
      expect(error).toBeInstanceOf(PlatformApiError);
      const platformError = error as PlatformApiError;
      expect(platformError.statusCode).toBe(0);
      expect(platformError.message).toContain('Platform API request failed');
    }
  });
});
