import { resolveValidationAccess } from '@/lib/validation/server/auth';
import {
  buildValidationIdempotencyKey,
  isValidValidationRunId,
  proxyValidationPlatformCallWithFallback,
} from '@/lib/validation/server/platform-api';
import type { CreateSharedValidationDecisionPayload } from '@/lib/validation/types';
import { NextResponse } from 'next/server';

export async function POST(request: Request, { params }: { params: Promise<{ runId: string }> }) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  const { runId } = await params;
  if (!isValidValidationRunId(runId)) {
    return NextResponse.json({ error: 'Invalid runId format' }, { status: 400 });
  }

  let payload: CreateSharedValidationDecisionPayload;
  try {
    payload = (await request.json()) as CreateSharedValidationDecisionPayload;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  return proxyValidationPlatformCallWithFallback({
    method: 'POST',
    paths: [`/v2/validation-sharing/runs/${runId}/decisions`],
    access: accessResult.access,
    body: payload,
    idempotencyKey:
      request.headers.get('Idempotency-Key') ?? buildValidationIdempotencyKey('shared-decision'),
  });
}
