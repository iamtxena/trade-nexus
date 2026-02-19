import type { NextRequest } from 'next/server';

import { resolveValidationAccess } from '@/lib/validation/server/auth';
import { proxyValidationPlatformCall } from '@/lib/validation/server/platform-api';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ runId: string }> },
) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  const { runId } = await params;
  return proxyValidationPlatformCall({
    method: 'GET',
    path: `/v2/validation-runs/${runId}`,
    access: accessResult.access,
  });
}
