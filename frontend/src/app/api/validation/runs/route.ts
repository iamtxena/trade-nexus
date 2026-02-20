import { type NextRequest, NextResponse } from 'next/server';

import { resolveValidationAccess } from '@/lib/validation/server/auth';
import {
  buildValidationIdempotencyKey,
  proxyValidationPlatformCall,
} from '@/lib/validation/server/platform-api';
import type { CreateValidationRunRequestPayload } from '@/lib/validation/types';

export async function GET(request: NextRequest) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  const requestId = accessResult.access.requestId;
  return NextResponse.json(
    {
      error: {
        code: 'VALIDATION_RUN_LIST_NOT_AVAILABLE',
        message:
          'Run list endpoint is not part of the frozen Platform API contract. Load runs by runId and use local review history for list UX.',
      },
      requestId,
      hint: {
        getRunStatus: `/api/validation/runs/${request.nextUrl.searchParams.get('runId') ?? ':runId'}`,
        getRunArtifact: `/api/validation/runs/${request.nextUrl.searchParams.get('runId') ?? ':runId'}/artifact`,
      },
    },
    { status: 405 },
  );
}

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
