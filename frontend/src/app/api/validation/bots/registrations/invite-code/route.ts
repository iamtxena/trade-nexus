import { resolveValidationAccess } from '@/lib/validation/server/auth';
import { proxyValidationPlatformCall } from '@/lib/validation/server/platform-api';
import type { CreateValidationBotInviteCodeRegistrationPayload } from '@/lib/validation/types';
import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  let payload: CreateValidationBotInviteCodeRegistrationPayload;
  try {
    payload = (await request.json()) as CreateValidationBotInviteCodeRegistrationPayload;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  return proxyValidationPlatformCall({
    method: 'POST',
    path: '/v2/validation-bots/registrations/invite-code',
    access: accessResult.access,
    body: payload,
    idempotencyKey: request.headers.get('Idempotency-Key') ?? crypto.randomUUID(),
  });
}
