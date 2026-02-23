import { resolveValidationAccess } from '@/lib/validation/server/auth';
import {
  buildValidationIdempotencyKey,
  isValidValidationRunId,
  proxyValidationPlatformCallWithFallback,
} from '@/lib/validation/server/platform-api';
import type { CreateSharedValidationCommentPayload } from '@/lib/validation/types';
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

  let payload: CreateSharedValidationCommentPayload;
  try {
    payload = (await request.json()) as CreateSharedValidationCommentPayload;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  return proxyValidationPlatformCallWithFallback({
    method: 'POST',
    paths: [
      `/v2/shared-validation/runs/${runId}/comments`,
      `/v2/validation-review/runs/${runId}/comments`,
    ],
    access: accessResult.access,
    body: payload,
    idempotencyKey:
      request.headers.get('Idempotency-Key') ?? buildValidationIdempotencyKey('shared-comment'),
  });
}
