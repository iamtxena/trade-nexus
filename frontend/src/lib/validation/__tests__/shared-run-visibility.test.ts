import { describe, expect, test } from 'bun:test';

import { filterRunsSharedWithMe } from '../shared-run-visibility';
import type { ValidationSharedRunSummary } from '../types';

function run(
  id: string,
  ownerUserId: string | undefined,
  updatedAt: string,
): ValidationSharedRunSummary {
  return {
    runId: id,
    permission: 'comment',
    status: 'completed',
    profile: 'STANDARD',
    finalDecision: 'pass',
    ownerUserId,
    createdAt: updatedAt,
    updatedAt,
  };
}

describe('filterRunsSharedWithMe', () => {
  test('hides owner-authored runs and keeps non-owned shared runs', () => {
    const input = [
      run('valrun-001', 'user-owner', '2026-02-21T10:00:00Z'),
      run('valrun-002', 'user-other', '2026-02-21T11:00:00Z'),
      run('valrun-003', undefined, '2026-02-21T12:00:00Z'),
    ];

    expect(filterRunsSharedWithMe(input, 'user-owner').map((item) => item.runId)).toEqual([
      'valrun-002',
      'valrun-003',
    ]);
  });
});
