import { beforeEach, describe, expect, mock, test } from 'bun:test';

import type {
  ValidationAccessContext,
  ValidationAccessResolution,
} from '@/lib/validation/server/auth';
import type { NextResponse } from 'next/server';

const ACCESS_CONTEXT: ValidationAccessContext = {
  requestId: 'req-web-shared-writes-001',
  userId: 'invitee-user-001',
  tenantId: 'tenant-shared-001',
  authMode: 'clerk_session',
};

const resolveValidationAccessMock = mock(async (): Promise<ValidationAccessResolution> => ({
  ok: true,
  access: ACCESS_CONTEXT,
}));
const proxyValidationPlatformCallWithFallbackMock = mock(async () =>
  new Response(JSON.stringify({ requestId: 'req-upstream-001' }), {
    status: 202,
    headers: { 'Content-Type': 'application/json' },
  }),
);

class MockNextResponse extends Response {
  static json(data: unknown, init?: ResponseInit): Response {
    return new Response(JSON.stringify(data), {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    });
  }
}

mock.module('next/server', () => ({
  NextResponse: MockNextResponse,
}));

mock.module('@/lib/validation/server/auth', () => ({
  resolveValidationAccess: resolveValidationAccessMock,
}));

mock.module('@/lib/validation/server/platform-api', () => ({
  buildValidationIdempotencyKey: (action: string) => `idem-web-${action}-generated`,
  isValidValidationRunId: (runId: string) => /^[a-zA-Z0-9_-]+$/.test(runId),
  proxyValidationPlatformCallWithFallback: proxyValidationPlatformCallWithFallbackMock,
}));

const commentsRouteModulePromise = import('../comments/route');
const decisionsRouteModulePromise = import('../decisions/route');

describe('shared validation write proxy routes', () => {
  beforeEach(() => {
    resolveValidationAccessMock.mockReset();
    proxyValidationPlatformCallWithFallbackMock.mockReset();
    resolveValidationAccessMock.mockResolvedValue({
      ok: true,
      access: ACCESS_CONTEXT,
    });
    proxyValidationPlatformCallWithFallbackMock.mockImplementation(async () =>
      new Response(JSON.stringify({ requestId: 'req-upstream-001' }), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
  });

  test('invitee shared comment flow proxies to canonical validation-sharing comment endpoint', async () => {
    const { POST } = await commentsRouteModulePromise;
    const payload = {
      body: 'Shared reviewer comment.',
      evidenceRefs: ['blob://validation/shared/comment-001.json'],
    };

    const response = await POST(
      new Request('https://app.local/api/shared-validation/runs/valrun-001/comments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }),
      {
        params: Promise.resolve({ runId: 'valrun-001' }),
      },
    );

    expect(response.status).toBe(202);
    expect(resolveValidationAccessMock).toHaveBeenCalledTimes(1);
    expect(proxyValidationPlatformCallWithFallbackMock).toHaveBeenCalledTimes(1);
    expect(proxyValidationPlatformCallWithFallbackMock).toHaveBeenCalledWith({
      method: 'POST',
      paths: ['/v2/validation-sharing/runs/valrun-001/comments'],
      access: ACCESS_CONTEXT,
      body: payload,
      idempotencyKey: 'idem-web-shared-comment-generated',
    });
  });

  test('invitee shared decision flow proxies to canonical validation-sharing decision endpoint', async () => {
    const { POST } = await decisionsRouteModulePromise;
    const payload = {
      action: 'approve',
      decision: 'conditional_pass',
      reason: 'Shared reviewer approved with caution.',
      evidenceRefs: ['blob://validation/shared/decision-001.json'],
    };

    const response = await POST(
      new Request('https://app.local/api/shared-validation/runs/valrun-001/decisions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': 'idem-shared-decision-explicit-001',
        },
        body: JSON.stringify(payload),
      }),
      {
        params: Promise.resolve({ runId: 'valrun-001' }),
      },
    );

    expect(response.status).toBe(202);
    expect(resolveValidationAccessMock).toHaveBeenCalledTimes(1);
    expect(proxyValidationPlatformCallWithFallbackMock).toHaveBeenCalledTimes(1);
    expect(proxyValidationPlatformCallWithFallbackMock).toHaveBeenCalledWith({
      method: 'POST',
      paths: ['/v2/validation-sharing/runs/valrun-001/decisions'],
      access: ACCESS_CONTEXT,
      body: payload,
      idempotencyKey: 'idem-shared-decision-explicit-001',
    });
  });

  test('shared write routes return auth response without proxying when access check fails', async () => {
    const { POST: commentPost } = await commentsRouteModulePromise;
    resolveValidationAccessMock.mockResolvedValue({
      ok: false,
      response: new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }) as unknown as NextResponse,
    });

    const response = await commentPost(
      new Request('https://app.local/api/shared-validation/runs/valrun-001/comments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ body: 'blocked' }),
      }),
      {
        params: Promise.resolve({ runId: 'valrun-001' }),
      },
    );

    expect(response.status).toBe(401);
    expect(proxyValidationPlatformCallWithFallbackMock).not.toHaveBeenCalled();
  });
});
