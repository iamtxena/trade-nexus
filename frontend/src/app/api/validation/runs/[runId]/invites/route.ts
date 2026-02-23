import { resolveValidationAccess } from '@/lib/validation/server/auth';
import {
  buildValidationIdempotencyKey,
  isValidValidationRunId,
  proxyValidationPlatformCallWithFallback,
} from '@/lib/validation/server/platform-api';
import type { CreateValidationShareInvitePayload } from '@/lib/validation/types';
import { NextResponse } from 'next/server';

export async function GET(request: Request, { params }: { params: Promise<{ runId: string }> }) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  const { runId } = await params;
  if (!isValidValidationRunId(runId)) {
    return NextResponse.json({ error: 'Invalid runId format' }, { status: 400 });
  }

  const query = new URL(request.url).searchParams.toString();
  const suffix = query ? `?${query}` : '';
  return proxyValidationPlatformCallWithFallback({
    method: 'GET',
    paths: [
      `/v2/validation-sharing/runs/${runId}/invites${suffix}`,
      `/v2/shared-validation/runs/${runId}/invites${suffix}`,
    ],
    access: accessResult.access,
  });
}

export async function POST(request: Request, { params }: { params: Promise<{ runId: string }> }) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  const { runId } = await params;
  if (!isValidValidationRunId(runId)) {
    return NextResponse.json({ error: 'Invalid runId format' }, { status: 400 });
  }

  let payload: CreateValidationShareInvitePayload;
  try {
    payload = (await request.json()) as CreateValidationShareInvitePayload;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  return proxyValidationPlatformCallWithFallback({
    method: 'POST',
    paths: [
      `/v2/validation-sharing/runs/${runId}/invites`,
      `/v2/shared-validation/runs/${runId}/invites`,
    ],
    access: accessResult.access,
    body: payload,
    idempotencyKey:
      request.headers.get('Idempotency-Key') ?? buildValidationIdempotencyKey('share-invite'),
  });
}
