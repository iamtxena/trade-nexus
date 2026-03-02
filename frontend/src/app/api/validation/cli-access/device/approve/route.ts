import { type NextRequest, NextResponse } from 'next/server';

import { resolveValidationAccess } from '@/lib/validation/server/auth';
import {
  buildValidationIdempotencyKey,
  proxyValidationPlatformCall,
} from '@/lib/validation/server/platform-api';
import type { CreateValidationCliDeviceApprovalPayload } from '@/lib/validation/types';

export async function POST(request: NextRequest) {
  const accessResult = await resolveValidationAccess();
  if (!accessResult.ok) {
    return accessResult.response;
  }

  let payload: CreateValidationCliDeviceApprovalPayload;
  try {
    payload = (await request.json()) as CreateValidationCliDeviceApprovalPayload;
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  if (typeof payload.userCode !== 'string' || payload.userCode.trim() === '') {
    return NextResponse.json({ error: 'userCode is required.' }, { status: 400 });
  }

  return proxyValidationPlatformCall({
    method: 'POST',
    path: '/v2/validation-cli-auth/device/approve',
    access: accessResult.access,
    body: {
      userCode: payload.userCode,
    },
    idempotencyKey:
      request.headers.get('Idempotency-Key') ?? buildValidationIdempotencyKey('cli-device-approve'),
  });
}
