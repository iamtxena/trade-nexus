import { resolveValidationAccess } from '@/lib/validation/server/auth';
import { proxyValidationPlatformCallWithFallback } from '@/lib/validation/server/platform-api';

export async function GET(request: Request) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  const query = new URL(request.url).searchParams.toString();
  const suffix = query ? `?${query}` : '';
  return proxyValidationPlatformCallWithFallback({
    method: 'GET',
    paths: [
      `/v2/validation-sharing/runs/shared-with-me${suffix}`,
      `/v2/shared-validation/runs${suffix}`,
      `/v2/validation-review/runs${suffix}`,
    ],
    access: accessResult.access,
  });
}
