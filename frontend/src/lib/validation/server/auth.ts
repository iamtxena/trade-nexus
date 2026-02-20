import { auth } from '@clerk/nextjs/server';
import { NextResponse } from 'next/server';

export interface ValidationAuthSnapshot {
  userId: string | null;
  orgId?: string | null;
  getToken?: () => Promise<string | null>;
}

export interface ValidationAccessContext {
  userId: string;
  tenantId: string;
  requestId: string;
  authorization?: string;
}

export type ValidationAuthReader = () => Promise<ValidationAuthSnapshot>;

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
  readAuth: ValidationAuthReader = auth as unknown as ValidationAuthReader,
): Promise<ValidationAccessResolution> {
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
      requestId: buildValidationRequestId(),
      authorization,
    },
  };
}
