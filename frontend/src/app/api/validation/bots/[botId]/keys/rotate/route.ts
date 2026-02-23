import { resolveValidationAccess } from '@/lib/validation/server/auth';
import { proxyValidationPlatformCall } from '@/lib/validation/server/platform-api';
import type { CreateValidationBotKeyRotationPayload } from '@/lib/validation/types';
import { NextResponse } from 'next/server';

function isValidIdentifier(value: string): boolean {
  return /^[a-zA-Z0-9_-]+$/.test(value);
}

export async function POST(request: Request, { params }: { params: Promise<{ botId: string }> }) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  const { botId } = await params;
  if (!isValidIdentifier(botId)) {
    return NextResponse.json({ error: 'Invalid botId format' }, { status: 400 });
  }

  let payload: CreateValidationBotKeyRotationPayload | undefined;
  try {
    payload = (await request.json()) as CreateValidationBotKeyRotationPayload;
  } catch {
    payload = undefined;
  }

  return proxyValidationPlatformCall({
    method: 'POST',
    path: `/v2/validation-bots/${botId}/keys/rotate`,
    access: accessResult.access,
    body: payload,
    idempotencyKey: request.headers.get('Idempotency-Key') ?? crypto.randomUUID(),
  });
}
