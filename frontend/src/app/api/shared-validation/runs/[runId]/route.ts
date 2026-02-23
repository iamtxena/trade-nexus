import { resolveValidationAccess } from '@/lib/validation/server/auth';
import {
  isValidValidationRunId,
  proxyValidationPlatformCallWithFallback,
} from '@/lib/validation/server/platform-api';
import { NextResponse } from 'next/server';

export async function GET(_request: Request, { params }: { params: Promise<{ runId: string }> }) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  const { runId } = await params;
  if (!isValidValidationRunId(runId)) {
    return NextResponse.json({ error: 'Invalid runId format' }, { status: 400 });
  }

  return proxyValidationPlatformCallWithFallback({
    method: 'GET',
    paths: [`/v2/shared-validation/runs/${runId}`, `/v2/validation-review/runs/${runId}`],
    access: accessResult.access,
  });
}
