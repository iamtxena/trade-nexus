import { beforeEach, describe, expect, mock, test } from 'bun:test';

import type {
  ValidationAccessContext,
  ValidationAccessResolution,
} from '@/lib/validation/server/auth';
import type { NextRequest, NextResponse } from 'next/server';

const ACCESS_CONTEXT: ValidationAccessContext = {
  requestId: 'req-web-cli-access-001',
  userId: 'user-cli-web-001',
  tenantId: 'tenant-cli-web-001',
  authMode: 'clerk_session',
};

const resolveValidationAccessMock = mock(
  async (): Promise<ValidationAccessResolution> => ({
    ok: true,
    access: ACCESS_CONTEXT,
  }),
);
const proxyValidationPlatformCallMock = mock(
  async () =>
    new Response(JSON.stringify({ requestId: 'req-upstream-001' }), {
      status: 200,
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
  buildValidationIdempotencyKey: (action: string) => `idem-${action}-generated`,
  isValidValidationCliSessionId: (sessionId: string) => /^[a-zA-Z0-9_-]+$/.test(sessionId),
  proxyValidationPlatformCall: proxyValidationPlatformCallMock,
}));

const listRouteModulePromise = import('../sessions/route');
const approveRouteModulePromise = import('../device/approve/route');
const revokeRouteModulePromise = import('../sessions/[sessionId]/revoke/route');

function asNextRequest(request: Request): NextRequest {
  return request as unknown as NextRequest;
}

describe('cli access route handlers', () => {
  beforeEach(() => {
    resolveValidationAccessMock.mockReset();
    proxyValidationPlatformCallMock.mockReset();
    resolveValidationAccessMock.mockResolvedValue({
      ok: true,
      access: ACCESS_CONTEXT,
    });
    proxyValidationPlatformCallMock.mockImplementation(
      async () =>
        new Response(JSON.stringify({ requestId: 'req-upstream-001' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    );
  });

  test('sessions GET proxies to validation-cli-auth sessions endpoint', async () => {
    const { GET } = await listRouteModulePromise;
    const response = await GET(
      asNextRequest(new Request('https://app.local/api/validation/cli-access/sessions')),
    );

    expect(response.status).toBe(200);
    expect(resolveValidationAccessMock).toHaveBeenCalledTimes(1);
    expect(proxyValidationPlatformCallMock).toHaveBeenCalledTimes(1);
    expect(proxyValidationPlatformCallMock).toHaveBeenCalledWith({
      method: 'GET',
      path: '/v2/validation-cli-auth/sessions',
      access: ACCESS_CONTEXT,
    });
  });

  test('approve POST validates body and sets generated idempotency key', async () => {
    const { POST } = await approveRouteModulePromise;
    const response = await POST(
      asNextRequest(
        new Request('https://app.local/api/validation/cli-access/device/approve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ userCode: 'ABCD-2345' }),
        }),
      ),
    );

    expect(response.status).toBe(200);
    expect(proxyValidationPlatformCallMock).toHaveBeenCalledWith({
      method: 'POST',
      path: '/v2/validation-cli-auth/device/approve',
      access: ACCESS_CONTEXT,
      body: {
        userCode: 'ABCD-2345',
      },
      idempotencyKey: 'idem-cli-device-approve-generated',
    });
  });

  test('approve POST returns 400 for invalid JSON body', async () => {
    const { POST } = await approveRouteModulePromise;
    const response = await POST(
      asNextRequest(
        new Request('https://app.local/api/validation/cli-access/device/approve', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: '{bad json',
        }),
      ),
    );

    expect(response.status).toBe(400);
    expect(proxyValidationPlatformCallMock).not.toHaveBeenCalled();
  });

  test('session revoke POST validates sessionId and forwards idempotency key', async () => {
    const { POST } = await revokeRouteModulePromise;
    const response = await POST(
      asNextRequest(
        new Request('https://app.local/api/validation/cli-access/sessions/clisess-001/revoke', {
          method: 'POST',
          headers: {
            'Idempotency-Key': 'idem-cli-revoke-explicit-001',
          },
        }),
      ),
      {
        params: Promise.resolve({ sessionId: 'clisess-001' }),
      },
    );

    expect(response.status).toBe(200);
    expect(proxyValidationPlatformCallMock).toHaveBeenCalledWith({
      method: 'POST',
      path: '/v2/validation-cli-auth/sessions/clisess-001/revoke',
      access: ACCESS_CONTEXT,
      idempotencyKey: 'idem-cli-revoke-explicit-001',
    });
  });

  test('session revoke POST returns 400 for invalid sessionId', async () => {
    const { POST } = await revokeRouteModulePromise;
    const response = await POST(
      asNextRequest(
        new Request('https://app.local/api/validation/cli-access/sessions/invalid/revoke', {
          method: 'POST',
        }),
      ),
      {
        params: Promise.resolve({ sessionId: 'bad id' }),
      },
    );

    expect(response.status).toBe(400);
    expect(proxyValidationPlatformCallMock).not.toHaveBeenCalled();
  });

  test('route handlers return auth response and skip proxy on access failure', async () => {
    const { GET } = await listRouteModulePromise;
    resolveValidationAccessMock.mockResolvedValue({
      ok: false,
      response: new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }) as unknown as NextResponse,
    });

    const response = await GET(
      asNextRequest(new Request('https://app.local/api/validation/cli-access/sessions')),
    );

    expect(response.status).toBe(401);
    expect(proxyValidationPlatformCallMock).not.toHaveBeenCalled();
  });
});
