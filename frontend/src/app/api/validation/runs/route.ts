import { type NextRequest, NextResponse } from 'next/server';

import { resolveValidationAccess } from '@/lib/validation/server/auth';
import {
  buildValidationIdempotencyKey,
  proxyValidationPlatformCall,
} from '@/lib/validation/server/platform-api';
import type { CreateValidationRunRequestPayload } from '@/lib/validation/types';

export async function POST(request: NextRequest) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  let payload: CreateValidationRunRequestPayload;
  try {
    payload = (await request.json()) as CreateValidationRunRequestPayload;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  return proxyValidationPlatformCall({
    method: 'POST',
    path: '/v2/validation-runs',
    access: accessResult.access,
    body: payload,
    idempotencyKey:
      request.headers.get('Idempotency-Key') ?? buildValidationIdempotencyKey('create-run'),
  });
}
