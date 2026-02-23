import { resolveValidationAccess } from '@/lib/validation/server/auth';
import { proxyValidationPlatformCallWithFallback } from '@/lib/validation/server/platform-api';

export async function GET() {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  return proxyValidationPlatformCallWithFallback({
    method: 'GET',
    paths: ['/v2/validation-bots', '/v2/bots'],
    access: accessResult.access,
  });
}
