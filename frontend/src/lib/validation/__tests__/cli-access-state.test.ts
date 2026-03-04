import { describe, expect, test } from 'bun:test';

import type { ValidationCliSession } from '@/lib/validation/types';

import {
  buildValidationCliPendingApprovalRows,
  formatValidationCliTimestamp,
  mapValidationCliSessionListResponse,
  normalizeValidationCliUserCode,
  readPendingCliDeviceRequests,
  removePendingCliDeviceRequest,
  resolveValidationCliUserCodeImport,
  upsertPendingCliDeviceRequest,
} from '../cli-access-state';

class MemoryStorage implements Pick<Storage, 'getItem' | 'setItem'> {
  private values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

function createSession(id: string, createdAt: string): ValidationCliSession {
  return {
    id,
    tenantId: 'tenant-001',
    userId: 'user-001',
    createdByUserId: 'user-001',
    scopes: ['validation:read'],
    createdAt,
    expiresAt: '2026-03-02T12:00:00Z',
    revokedAt: null,
    lastUsedAt: null,
  };
}

describe('normalizeValidationCliUserCode', () => {
  test('normalizes compact and dashed formats', () => {
    expect(normalizeValidationCliUserCode('abcd2345')).toBe('ABCD-2345');
    expect(normalizeValidationCliUserCode('ab-cd-23-45')).toBe('ABCD-2345');
  });

  test('rejects invalid alphabet or length', () => {
    expect(normalizeValidationCliUserCode('ABCD1234')).toBeNull();
    expect(normalizeValidationCliUserCode('ABC1234')).toBeNull();
  });
});

describe('pending request storage', () => {
  test('upsert persists and deduplicates by userCode', () => {
    const storage = new MemoryStorage();
    const ownerScope = 'user-123';
    upsertPendingCliDeviceRequest(ownerScope, 'ABCD2345', storage);
    const next = upsertPendingCliDeviceRequest(ownerScope, 'ABCD-2345', storage);
    expect(next).toHaveLength(1);
    expect(next[0]?.userCode).toBe('ABCD-2345');
  });

  test('remove deletes a pending request for owner scope', () => {
    const storage = new MemoryStorage();
    const ownerScope = 'user-123';
    upsertPendingCliDeviceRequest(ownerScope, 'ABCD2345', storage);
    upsertPendingCliDeviceRequest(ownerScope, 'EFGH2345', storage);

    const next = removePendingCliDeviceRequest(ownerScope, 'ABCD-2345', storage);
    expect(next.map((item) => item.userCode)).toEqual(['EFGH-2345']);
  });

  test('read ignores invalid payload values', () => {
    const storage = new MemoryStorage();
    storage.setItem(
      'trade-nexus.validation.cli-access.pending.v1:user-123',
      JSON.stringify([{ userCode: 'invalid', requestedAt: 'not-a-time' }]),
    );
    expect(readPendingCliDeviceRequests('user-123', storage)).toEqual([]);
  });

  test('auto-queue request appears in pending rows with approve action visible', () => {
    const storage = new MemoryStorage();
    upsertPendingCliDeviceRequest('user-123', 'ABCD-2345', storage);

    const pendingRows = buildValidationCliPendingApprovalRows(
      readPendingCliDeviceRequests('user-123', storage),
    );
    expect(pendingRows).toHaveLength(1);
    expect(pendingRows[0]).toMatchObject({
      userCode: 'ABCD-2345',
      showApproveAction: true,
    });
  });
});

describe('resolveValidationCliUserCodeImport', () => {
  test('re-queues user_code when owner scope changes after sign-in', () => {
    const importedAsAnonymous = resolveValidationCliUserCodeImport({
      ownerScope: 'anonymous',
      urlUserCode: 'ABCD-2345',
      previousImportedKey: null,
    });
    expect(importedAsAnonymous).toMatchObject({
      normalizedUserCode: 'ABCD-2345',
      shouldQueue: true,
    });

    const importedAfterSignIn = resolveValidationCliUserCodeImport({
      ownerScope: 'user-123',
      urlUserCode: 'ABCD-2345',
      previousImportedKey: importedAsAnonymous.nextImportedKey,
    });
    expect(importedAfterSignIn).toMatchObject({
      normalizedUserCode: 'ABCD-2345',
      shouldQueue: true,
    });
  });

  test('skips duplicate queue for same owner scope and code', () => {
    const firstImport = resolveValidationCliUserCodeImport({
      ownerScope: 'user-123',
      urlUserCode: 'ABCD-2345',
      previousImportedKey: null,
    });
    expect(firstImport.shouldQueue).toBe(true);

    const duplicateImport = resolveValidationCliUserCodeImport({
      ownerScope: 'user-123',
      urlUserCode: 'ABCD-2345',
      previousImportedKey: firstImport.nextImportedKey,
    });
    expect(duplicateImport.shouldQueue).toBe(false);
    expect(duplicateImport.nextImportedKey).toBe(firstImport.nextImportedKey);
  });
});

describe('mapValidationCliSessionListResponse', () => {
  test('returns sessions sorted by createdAt desc', () => {
    const response = {
      requestId: 'req-001',
      sessions: [
        createSession('clisess-001', '2026-03-02T10:00:00Z'),
        createSession('clisess-002', '2026-03-02T11:00:00Z'),
      ],
    };
    expect(mapValidationCliSessionListResponse(response).map((session) => session.id)).toEqual([
      'clisess-002',
      'clisess-001',
    ]);
  });
});

describe('formatValidationCliTimestamp', () => {
  test('formats known timestamp as UTC label', () => {
    expect(formatValidationCliTimestamp('2026-03-02T11:00:00Z')).toBe('2026-03-02 11:00:00 UTC');
  });

  test('returns Unknown for invalid values', () => {
    expect(formatValidationCliTimestamp('invalid')).toBe('Unknown');
    expect(formatValidationCliTimestamp(undefined)).toBe('Unknown');
  });
});
