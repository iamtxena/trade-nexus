import { describe, expect, test } from 'bun:test';

import type { ValidationRunSummary } from '@/lib/validation/types';

import { readReviewRunHistory, upsertReviewRunHistory } from '../review-run-history';

class MemoryStorage implements Pick<Storage, 'getItem' | 'setItem'> {
  private values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }
}

function createRun(id: string, overrides?: Partial<ValidationRunSummary>): ValidationRunSummary {
  return {
    id,
    status: 'queued',
    profile: 'STANDARD',
    schemaVersion: 'validation-run.v1',
    finalDecision: 'fail',
    createdAt: '2026-02-18T10:00:00Z',
    updatedAt: '2026-02-18T10:00:00Z',
    ...overrides,
  };
}

describe('readReviewRunHistory', () => {
  test('returns empty list for empty storage', () => {
    const storage = new MemoryStorage();
    expect(readReviewRunHistory(storage)).toEqual([]);
  });

  test('ignores invalid payload shapes', () => {
    const storage = new MemoryStorage();
    storage.setItem('trade-nexus.validation.review.run-history.v1', JSON.stringify([{ id: 1 }]));

    expect(readReviewRunHistory(storage)).toEqual([]);
  });
});

describe('upsertReviewRunHistory', () => {
  test('stores run and returns timestamp-sorted list', () => {
    const storage = new MemoryStorage();
    const runA = createRun('valrun-001', { updatedAt: '2026-02-18T10:00:00Z' });
    const runB = createRun('valrun-002', { updatedAt: '2026-02-18T12:00:00Z' });

    upsertReviewRunHistory(runA, storage);
    const result = upsertReviewRunHistory(runB, storage);

    expect(result.map((run) => run.id)).toEqual(['valrun-002', 'valrun-001']);
  });

  test('updates existing run by id instead of duplicating', () => {
    const storage = new MemoryStorage();
    const initial = createRun('valrun-001', {
      status: 'queued',
      updatedAt: '2026-02-18T10:00:00Z',
    });
    const updated = createRun('valrun-001', {
      status: 'completed',
      updatedAt: '2026-02-18T11:00:00Z',
      finalDecision: 'pass',
    });

    upsertReviewRunHistory(initial, storage);
    const result = upsertReviewRunHistory(updated, storage);

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual(updated);
  });
});
