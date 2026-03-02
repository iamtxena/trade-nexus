import type { NextRequest } from 'next/server';

import { resolveValidationAccess } from '@/lib/validation/server/auth';
import { proxyValidationPlatformCall } from '@/lib/validation/server/platform-api';

export async function GET(_request: NextRequest) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  return proxyValidationPlatformCall({
    method: 'GET',
    path: '/v2/validation-cli-auth/sessions',
    access: accessResult.access,
  });
}
