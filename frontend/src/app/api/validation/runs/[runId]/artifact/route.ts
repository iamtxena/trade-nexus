import { type NextRequest, NextResponse } from 'next/server';

import { resolveValidationAccess } from '@/lib/validation/server/auth';
import {
  isValidValidationRunId,
  proxyValidationPlatformCall,
} from '@/lib/validation/server/platform-api';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> },
) {
  const accessResult = await resolveValidationAccess({
    requestHeaders: request.headers,
    allowSmokeKey: true,
  });
  if (!accessResult.ok) {
    return accessResult.response;
  }

  const { runId } = await params;
  if (!isValidValidationRunId(runId)) {
    return NextResponse.json({ error: 'Invalid runId format' }, { status: 400 });
  }
  return proxyValidationPlatformCall({
    method: 'GET',
    path: `/v2/validation-runs/${runId}/artifact`,
    access: accessResult.access,
  });
}
