import { resolveValidationAccess } from '@/lib/validation/server/auth';
import {
  buildValidationIdempotencyKey,
  proxyValidationPlatformCallWithFallback,
} from '@/lib/validation/server/platform-api';
import { NextResponse } from 'next/server';

function isValidInviteId(value: string): boolean {
  return /^[a-zA-Z0-9_-]+$/.test(value);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ inviteId: string }> },
) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  const { inviteId } = await params;
  if (!isValidInviteId(inviteId)) {
    return NextResponse.json({ error: 'Invalid inviteId format' }, { status: 400 });
  }

  return proxyValidationPlatformCallWithFallback({
    method: 'POST',
    paths: [
      `/v2/validation-sharing/invites/${inviteId}/revoke`,
      `/v2/shared-validation/invites/${inviteId}/revoke`,
    ],
    access: accessResult.access,
    idempotencyKey:
      request.headers.get('Idempotency-Key') ?? buildValidationIdempotencyKey('share-revoke'),
  });
}
