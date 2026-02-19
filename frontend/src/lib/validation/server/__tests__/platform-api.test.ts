import { describe, expect, mock, test } from 'bun:test';

import {
  buildValidationIdempotencyKey,
  callValidationPlatform,
  isValidValidationRunId,
  proxyValidationPlatformCall,
} from '../platform-api';

function getHeader(headers: RequestInit['headers'], key: string): string | null {
  if (!headers) {
    return null;
  }
  if (headers instanceof Headers) {
    return headers.get(key);
  }
  if (Array.isArray(headers)) {
    const entry = headers.find(([candidate]) => candidate.toLowerCase() === key.toLowerCase());
    return entry ? entry[1] : null;
  }
  const record = headers as Record<string, string>;
  return record[key] ?? record[key.toLowerCase()] ?? null;
}

describe('callValidationPlatform', () => {
  test('forwards method, payload, and identity headers to Platform API', async () => {
    const fetchMock = mock(() =>
      Promise.resolve(
        new Response(JSON.stringify({ requestId: 'req-v2-001' }), {
          status: 202,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    await callValidationPlatform({
      method: 'POST',
      path: '/v2/validation-runs/valrun-001/review',
      body: {
        reviewerType: 'trader',
        decision: 'conditional_pass',
        comments: ['Needs guardrails'],
      },
      idempotencyKey: 'idem-web-review-001',
      backendBaseUrl: 'https://api.trade-nexus.local/',
      access: {
        userId: 'user-001',
        tenantId: 'tenant-001',
        requestId: 'req-web-validation-001',
        authorization: 'Bearer token-001',
      },
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const firstCall = fetchMock.mock.calls[0] as unknown;
    const [url, requestInit] = firstCall as [string, RequestInit];
    expect(url).toBe('https://api.trade-nexus.local/v2/validation-runs/valrun-001/review');
    expect(requestInit.method).toBe('POST');
    expect(getHeader(requestInit.headers, 'X-Request-Id')).toBe('req-web-validation-001');
    expect(getHeader(requestInit.headers, 'X-Tenant-Id')).toBe('tenant-001');
    expect(getHeader(requestInit.headers, 'X-User-Id')).toBe('user-001');
    expect(getHeader(requestInit.headers, 'Authorization')).toBe('Bearer token-001');
    expect(getHeader(requestInit.headers, 'Idempotency-Key')).toBe('idem-web-review-001');
    expect(getHeader(requestInit.headers, 'Content-Type')).toBe('application/json');
    expect(requestInit.body).toBe(
      JSON.stringify({
        reviewerType: 'trader',
        decision: 'conditional_pass',
        comments: ['Needs guardrails'],
      }),
    );
  });

  test('forwards list-run GET call without request body', async () => {
    const fetchMock = mock(() =>
      Promise.resolve(
        new Response(JSON.stringify({ requestId: 'req-v2-004', runs: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    await callValidationPlatform({
      method: 'GET',
      path: '/v2/validation-runs?limit=25',
      backendBaseUrl: 'https://api.trade-nexus.local/',
      access: {
        userId: 'user-004',
        tenantId: 'tenant-004',
        requestId: 'req-web-validation-004',
      },
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const firstCall = fetchMock.mock.calls[0] as unknown;
    const [url, requestInit] = firstCall as [string, RequestInit];
    expect(url).toBe('https://api.trade-nexus.local/v2/validation-runs?limit=25');
    expect(requestInit.method).toBe('GET');
    expect(getHeader(requestInit.headers, 'X-Request-Id')).toBe('req-web-validation-004');
    expect(getHeader(requestInit.headers, 'X-Tenant-Id')).toBe('tenant-004');
    expect(getHeader(requestInit.headers, 'X-User-Id')).toBe('user-004');
    expect(getHeader(requestInit.headers, 'Content-Type')).toBeNull();
    expect(requestInit.body).toBeUndefined();
  });
});

describe('proxyValidationPlatformCall', () => {
  test('preserves backend status and json payload', async () => {
    const fetchMock = mock(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            error: {
              code: 'VALIDATION_REVIEW_STATE_INVALID',
              message: 'Trader review is not required for this run profile.',
            },
            requestId: 'req-v2-409',
          }),
          {
            status: 409,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      ),
    );

    const response = await proxyValidationPlatformCall({
      method: 'POST',
      path: '/v2/validation-runs/valrun-002/review',
      body: {
        reviewerType: 'trader',
        decision: 'pass',
      },
      idempotencyKey: buildValidationIdempotencyKey('review'),
      backendBaseUrl: 'https://api.trade-nexus.local',
      access: {
        userId: 'user-002',
        tenantId: 'tenant-002',
        requestId: 'req-web-validation-002',
      },
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    expect(response.status).toBe(409);
    expect(await response.json()).toEqual({
      error: {
        code: 'VALIDATION_REVIEW_STATE_INVALID',
        message: 'Trader review is not required for this run profile.',
      },
      requestId: 'req-v2-409',
    });
  });

  test('returns 502 when upstream call throws', async () => {
    const fetchMock = mock(() => Promise.reject(new Error('backend timeout')));

    const response = await proxyValidationPlatformCall({
      method: 'GET',
      path: '/v2/validation-runs/valrun-003',
      backendBaseUrl: 'https://api.trade-nexus.local',
      access: {
        userId: 'user-003',
        tenantId: 'tenant-003',
        requestId: 'req-web-validation-003',
      },
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ error: 'backend timeout' });
  });
});

describe('isValidValidationRunId', () => {
  test('accepts alphanumeric, underscore, and hyphen run ids', () => {
    expect(isValidValidationRunId('valrun_001-ABC')).toBe(true);
  });

  test('rejects path traversal and slash characters', () => {
    expect(isValidValidationRunId('../etc/passwd')).toBe(false);
    expect(isValidValidationRunId('run/child')).toBe(false);
  });
});
