import { describe, expect, test } from 'bun:test';

import { resolveValidationAccess } from '../auth';

describe('resolveValidationAccess', () => {
  test('returns unauthorized response when userId is missing', async () => {
    const result = await resolveValidationAccess({
      readAuth: async () => ({
        userId: null,
        orgId: null,
      }),
    });

    expect(result.ok).toBe(false);
    if (result.ok) {
      throw new Error('Expected access denial.');
    }
    expect(result.response.status).toBe(401);
    expect(await result.response.json()).toEqual({ error: 'Unauthorized' });
  });

  test('builds access context when userId and orgId are present', async () => {
    const result = await resolveValidationAccess({
      readAuth: async () => ({
        userId: 'user-123',
        orgId: 'tenant-abc',
        getToken: async () => 'token-xyz',
      }),
    });

    expect(result.ok).toBe(true);
    if (!result.ok) {
      throw new Error('Expected access grant.');
    }
    expect(result.access.userId).toBe('user-123');
    expect(result.access.tenantId).toBe('tenant-abc');
    expect(result.access.authorization).toBe('Bearer token-xyz');
    expect(result.access.authMode).toBe('clerk_session');
    expect(result.access.requestId.startsWith('req-web-validation-')).toBe(true);
  });

  test('falls back to derived tenant id when orgId is missing', async () => {
    const result = await resolveValidationAccess({
      readAuth: async () => ({
        userId: 'user-456',
        orgId: null,
      }),
    });

    expect(result.ok).toBe(true);
    if (!result.ok) {
      throw new Error('Expected access grant.');
    }
    expect(result.access.tenantId).toBe('tenant-clerk-user-456');
    expect(result.access.authorization).toBeUndefined();
  });

  test('resolves smoke shared-key access without Clerk session', async () => {
    const previous = process.env.VALIDATION_PROXY_SMOKE_SHARED_KEY;
    process.env.VALIDATION_PROXY_SMOKE_SHARED_KEY = 'smoke-shared-key';
    try {
      const result = await resolveValidationAccess({
        allowSmokeKey: true,
        requestHeaders: new Headers({
          'x-validation-smoke-key': 'smoke-shared-key',
          'x-api-key': 'tnx.bot.smoke.key-001',
        }),
      });
      expect(result.ok).toBe(true);
      if (!result.ok) {
        throw new Error('Expected access grant.');
      }
      expect(result.access.authMode).toBe('smoke_shared_key');
      expect(result.access.apiKey).toBe('tnx.bot.smoke.key-001');
      expect(result.access.authorization).toBeUndefined();
      expect(result.access.userId).toBeUndefined();
      expect(result.access.tenantId).toBeUndefined();
    } finally {
      process.env.VALIDATION_PROXY_SMOKE_SHARED_KEY = previous;
    }
  });

  test('allows smoke shared-key access without runtime bot key when explicitly enabled', async () => {
    const previous = process.env.VALIDATION_PROXY_SMOKE_SHARED_KEY;
    process.env.VALIDATION_PROXY_SMOKE_SHARED_KEY = 'smoke-shared-key';
    try {
      const result = await resolveValidationAccess({
        allowSmokeKey: true,
        allowSmokeKeyWithoutApiKey: true,
        requestHeaders: new Headers({
          'x-validation-smoke-key': 'smoke-shared-key',
        }),
      });
      expect(result.ok).toBe(true);
      if (!result.ok) {
        throw new Error('Expected access grant.');
      }
      expect(result.access.authMode).toBe('smoke_shared_key');
      expect(result.access.apiKey).toBeUndefined();
    } finally {
      process.env.VALIDATION_PROXY_SMOKE_SHARED_KEY = previous;
    }
  });

  test('rejects smoke shared-key access without runtime bot key when not enabled', async () => {
    const previous = process.env.VALIDATION_PROXY_SMOKE_SHARED_KEY;
    process.env.VALIDATION_PROXY_SMOKE_SHARED_KEY = 'smoke-shared-key';
    try {
      const result = await resolveValidationAccess({
        allowSmokeKey: true,
        requestHeaders: new Headers({
          'x-validation-smoke-key': 'smoke-shared-key',
        }),
        readAuth: async () => ({
          userId: null,
          orgId: null,
        }),
      });
      expect(result.ok).toBe(false);
      if (result.ok) {
        throw new Error('Expected access denial.');
      }
      expect(result.response.status).toBe(401);
    } finally {
      process.env.VALIDATION_PROXY_SMOKE_SHARED_KEY = previous;
    }
  });
});
