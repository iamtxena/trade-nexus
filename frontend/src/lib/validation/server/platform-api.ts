import { NextResponse } from 'next/server';

import type { ValidationAccessContext } from '@/lib/validation/server/auth';

type ValidationHttpMethod = 'GET' | 'POST';

interface ValidationPlatformCallOptions {
  method: ValidationHttpMethod;
  path: string;
  access: ValidationAccessContext;
  body?: unknown;
  idempotencyKey?: string;
  fetchImpl?: typeof fetch;
  backendBaseUrl?: string;
}

const DEFAULT_PLATFORM_BASE_URL = process.env.ML_BACKEND_URL ?? 'http://localhost:8000';

function resolveBaseUrl(baseUrl: string): string {
  if (baseUrl.endsWith('/')) {
    return baseUrl.slice(0, -1);
  }
  return baseUrl;
}

function resolvePath(path: string): string {
  return path.startsWith('/') ? path : `/${path}`;
}

export function buildValidationIdempotencyKey(action: string): string {
  return `idem-web-validation-${action}-${crypto.randomUUID()}`;
}

export async function callValidationPlatform(
  options: ValidationPlatformCallOptions,
): Promise<Response> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const baseUrl = resolveBaseUrl(options.backendBaseUrl ?? DEFAULT_PLATFORM_BASE_URL);
  const path = resolvePath(options.path);
  const url = `${baseUrl}${path}`;
  const headers = new Headers();

  headers.set('Accept', 'application/json');
  headers.set('X-Request-Id', options.access.requestId);
  headers.set('X-Tenant-Id', options.access.tenantId);
  headers.set('X-User-Id', options.access.userId);
  if (options.access.authorization) {
    headers.set('Authorization', options.access.authorization);
  }
  if (options.idempotencyKey) {
    headers.set('Idempotency-Key', options.idempotencyKey);
  }

  let body: string | undefined;
  if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json');
    body = JSON.stringify(options.body);
  }

  return fetchImpl(url, {
    method: options.method,
    headers,
    body,
    cache: 'no-store',
  });
}

async function toNextProxyResponse(response: Response): Promise<NextResponse> {
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    const payload = await response.json();
    return NextResponse.json(payload, { status: response.status });
  }

  const payload = await response.text();
  if (payload.length === 0) {
    return new NextResponse(null, { status: response.status });
  }

  return new NextResponse(payload, {
    status: response.status,
    headers: contentType ? { 'Content-Type': contentType } : undefined,
  });
}

export async function proxyValidationPlatformCall(
  options: ValidationPlatformCallOptions,
): Promise<NextResponse> {
  try {
    const response = await callValidationPlatform(options);
    return await toNextProxyResponse(response);
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Validation platform request failed',
      },
      { status: 502 },
    );
  }
}
