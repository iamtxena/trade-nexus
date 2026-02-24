import { auth } from '@clerk/nextjs/server';
import { NextResponse } from 'next/server';

import { resolveValidationSmokeApiKey } from '@/lib/validation/server/smoke-auth';

export interface ValidationAuthSnapshot {
  userId: string | null;
  orgId?: string | null;
  getToken?: () => Promise<string | null>;
}

export interface ValidationAccessContext {
  requestId: string;
  userId?: string;
  tenantId?: string;
  authorization?: string;
  apiKey?: string;
  authMode: 'clerk_session' | 'smoke_shared_key';
}

export type ValidationAuthReader = () => Promise<ValidationAuthSnapshot>;

export interface ResolveValidationAccessOptions {
  readAuth?: ValidationAuthReader;
  requestHeaders?: Pick<Headers, 'get'>;
  allowSmokeKey?: boolean;
}

export type ValidationAccessResolution =
  | { ok: true; access: ValidationAccessContext }
  | { ok: false; response: NextResponse };

function buildTenantId(orgId: string | null | undefined, userId: string): string {
  const normalizedOrg = orgId?.trim();
  if (normalizedOrg) {
    return normalizedOrg;
  }
  return `tenant-clerk-${userId}`;
}

export function buildValidationRequestId(): string {
  return `req-web-validation-${crypto.randomUUID()}`;
}

export async function resolveValidationAccess(
  options: ResolveValidationAccessOptions = {},
): Promise<ValidationAccessResolution> {
  const requestId = buildValidationRequestId();

  if (options.allowSmokeKey && options.requestHeaders) {
    const smokeApiKey = resolveValidationSmokeApiKey(options.requestHeaders);
    if (smokeApiKey) {
      return {
        ok: true,
        access: {
          requestId,
          apiKey: smokeApiKey,
          authMode: 'smoke_shared_key',
        },
      };
    }
  }

  const readAuth = options.readAuth ?? (auth as unknown as ValidationAuthReader);
  const snapshot = await readAuth();
  const userId = snapshot.userId?.trim() ?? null;
  if (!userId) {
    return {
      ok: false,
      response: NextResponse.json({ error: 'Unauthorized' }, { status: 401 }),
    };
  }

  const token = typeof snapshot.getToken === 'function' ? await snapshot.getToken() : null;
  const authorization = token ? `Bearer ${token}` : undefined;

  return {
    ok: true,
    access: {
      userId,
      tenantId: buildTenantId(snapshot.orgId, userId),
      requestId,
      authorization,
      authMode: 'clerk_session',
    },
  };
}
