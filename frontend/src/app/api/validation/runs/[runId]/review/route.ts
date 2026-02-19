import { type NextRequest, NextResponse } from 'next/server';

import { resolveValidationAccess } from '@/lib/validation/server/auth';
import {
  buildValidationIdempotencyKey,
  proxyValidationPlatformCall,
} from '@/lib/validation/server/platform-api';
import type { ValidationRunReviewRequestPayload } from '@/lib/validation/types';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> },
) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  let payload: ValidationRunReviewRequestPayload;
  try {
    payload = (await request.json()) as ValidationRunReviewRequestPayload;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { runId } = await params;
  return proxyValidationPlatformCall({
    method: 'POST',
    path: `/v2/validation-runs/${runId}/review`,
    access: accessResult.access,
    body: payload,
    idempotencyKey:
      request.headers.get('Idempotency-Key') ?? buildValidationIdempotencyKey('submit-review'),
  });
}
