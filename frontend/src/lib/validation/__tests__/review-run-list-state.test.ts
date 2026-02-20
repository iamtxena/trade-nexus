import { describe, expect, test } from 'bun:test';

import {
  resolveRunIdForListToDetailTransition,
  sortValidationRunsByUpdatedAtDesc,
} from '../review-run-list-state';
import type { ValidationRunSummary } from '../types';

function makeRun(id: string, updatedAt: string): ValidationRunSummary {
  return {
    id,
    status: 'completed',
    profile: 'STANDARD',
    schemaVersion: 'validation-run.v1',
    finalDecision: 'pass',
    createdAt: updatedAt,
    updatedAt,
  };
}

describe('resolveRunIdForListToDetailTransition', () => {
  const runs = sortValidationRunsByUpdatedAtDesc([
    makeRun('valrun-001', '2026-02-18T10:00:00Z'),
    makeRun('valrun-002', '2026-02-19T10:00:00Z'),
    makeRun('valrun-003', '2026-02-17T10:00:00Z'),
  ]);

  test('uses explicit list selection for list-to-detail transition', () => {
    expect(resolveRunIdForListToDetailTransition(runs, 'valrun-001', 'valrun-002')).toBe(
      'valrun-001',
    );
  });

  test('falls back to active run when explicit selection is missing', () => {
    expect(resolveRunIdForListToDetailTransition(runs, 'missing-run', 'valrun-002')).toBe(
      'valrun-002',
    );
  });

  test('falls back to newest run when neither explicit nor active run is present', () => {
    expect(resolveRunIdForListToDetailTransition(runs, null, null)).toBe('valrun-002');
  });

  test('returns null when run list is empty', () => {
    expect(resolveRunIdForListToDetailTransition([], null, null)).toBeNull();
  });
});
