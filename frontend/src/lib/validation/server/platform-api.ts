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

const VALIDATION_RUN_ID_PATTERN = /^[a-zA-Z0-9_-]+$/;

function isDeployedEnvironment(): boolean {
  const vercelEnv = process.env.VERCEL_ENV;
  // vercel dev sets VERCEL_ENV=development — treat that as local
  if (vercelEnv && vercelEnv !== 'development') return true;
  return process.env.NODE_ENV === 'production';
}

function resolvePlatformBaseUrl(): string {
  const url = process.env.ML_BACKEND_URL;

  if (!url) {
    if (isDeployedEnvironment()) {
      throw new Error(
        'ML_BACKEND_URL is not set. This environment variable is required in deployed environments. ' +
          'Set it to the ML backend origin (e.g. https://api-nexus.lona.agency).',
      );
    }
    // Local development fallback
    return 'http://localhost:8000';
  }

  if (
    isDeployedEnvironment() &&
    (url.includes('localhost') || url.includes('127.0.0.1'))
  ) {
    throw new Error(
      `ML_BACKEND_URL points to a local address (${url}) in a production environment. ` +
        'Set it to the ML backend origin (e.g. https://api-nexus.lona.agency).',
    );
  }

  return url;
}

const DEFAULT_PLATFORM_BASE_URL = resolvePlatformBaseUrl();

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

export function isValidValidationRunId(runId: string): boolean {
  return VALIDATION_RUN_ID_PATTERN.test(runId);
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

interface ValidationFallbackProxyOptions extends Omit<ValidationPlatformCallOptions, 'path'> {
  paths: string[];
}

const FALLBACK_CONTINUE_STATUSES = new Set([404, 405, 501]);

export async function proxyValidationPlatformCallWithFallback(
  options: ValidationFallbackProxyOptions,
): Promise<NextResponse> {
  let lastResponse: NextResponse | null = null;

  for (const path of options.paths) {
    const response = await proxyValidationPlatformCall({
      ...options,
      path,
    });
    lastResponse = response;
    if (!FALLBACK_CONTINUE_STATUSES.has(response.status)) {
      return response;
    }
  }

  return (
    lastResponse ??
    NextResponse.json(
      {
        error: 'No validation platform endpoint path configured.',
      },
      { status: 502 },
    )
  );
}
