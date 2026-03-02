import { type NextRequest, NextResponse } from 'next/server';

import { resolveValidationAccess } from '@/lib/validation/server/auth';
import {
  buildValidationIdempotencyKey,
  isValidValidationCliSessionId,
  proxyValidationPlatformCall,
} from '@/lib/validation/server/platform-api';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ sessionId: string }> },
) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  const { sessionId } = await params;
  if (!isValidValidationCliSessionId(sessionId)) {
    return NextResponse.json({ error: 'Invalid sessionId format' }, { status: 400 });
  }

  return proxyValidationPlatformCall({
    method: 'POST',
    path: `/v2/validation-cli-auth/sessions/${sessionId}/revoke`,
    access: accessResult.access,
    idempotencyKey:
      request.headers.get('Idempotency-Key') ?? buildValidationIdempotencyKey('cli-session-revoke'),
  });
}
