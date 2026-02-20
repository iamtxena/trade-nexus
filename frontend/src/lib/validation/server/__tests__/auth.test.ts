import { describe, expect, test } from 'bun:test';

import { resolveValidationAccess } from '../auth';

describe('resolveValidationAccess', () => {
  test('returns unauthorized response when userId is missing', async () => {
    const result = await resolveValidationAccess(async () => ({
      userId: null,
      orgId: null,
    }));

    expect(result.ok).toBe(false);
    if (result.ok) {
      throw new Error('Expected access denial.');
    }
    expect(result.response.status).toBe(401);
    expect(await result.response.json()).toEqual({ error: 'Unauthorized' });
  });

  test('builds access context when userId and orgId are present', async () => {
    const result = await resolveValidationAccess(async () => ({
      userId: 'user-123',
      orgId: 'tenant-abc',
      getToken: async () => 'token-xyz',
    }));

    expect(result.ok).toBe(true);
    if (!result.ok) {
      throw new Error('Expected access grant.');
    }
    expect(result.access.userId).toBe('user-123');
    expect(result.access.tenantId).toBe('tenant-abc');
    expect(result.access.authorization).toBe('Bearer token-xyz');
    expect(result.access.requestId.startsWith('req-web-validation-')).toBe(true);
  });

  test('falls back to derived tenant id when orgId is missing', async () => {
    const result = await resolveValidationAccess(async () => ({
      userId: 'user-456',
      orgId: null,
    }));

    expect(result.ok).toBe(true);
    if (!result.ok) {
      throw new Error('Expected access grant.');
    }
    expect(result.access.tenantId).toBe('tenant-clerk-user-456');
    expect(result.access.authorization).toBeUndefined();
  });
});
