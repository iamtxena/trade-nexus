import { resolveValidationAccess } from '@/lib/validation/server/auth';
import { proxyValidationPlatformCall } from '@/lib/validation/server/platform-api';
import type { CreateValidationBotPartnerBootstrapPayload } from '@/lib/validation/types';
import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  const accessResult = await resolveValidationAccess({
    requestHeaders: request.headers,
    allowSmokeKey: true,
    allowSmokeKeyWithoutApiKey: true,
  });
  if (!accessResult.ok) {
    return accessResult.response;
  }

  let payload: CreateValidationBotPartnerBootstrapPayload;
  try {
    payload = (await request.json()) as CreateValidationBotPartnerBootstrapPayload;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  return proxyValidationPlatformCall({
    method: 'POST',
    path: '/v2/validation-bots/registrations/partner-bootstrap',
    access: accessResult.access,
    body: payload,
    idempotencyKey: request.headers.get('Idempotency-Key') ?? crypto.randomUUID(),
  });
}
