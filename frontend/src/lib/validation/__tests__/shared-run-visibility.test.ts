import { describe, expect, test } from 'bun:test';

import {
  DEFAULT_SHARED_RUN_LIST_FILTERS,
  filterRunsSharedWithMe,
  filterSharedRunsForDisplay,
} from '../shared-run-visibility';
import type { ValidationSharedRunSummary } from '../types';

function run(
  id: string,
  ownerUserId: string | undefined,
  updatedAt: string,
): ValidationSharedRunSummary {
  return {
    runId: id,
    permission: 'review',
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

  test('filterSharedRunsForDisplay applies query and facet filters', () => {
    const input = [
      run('valrun-001', 'user-owner', '2026-02-21T10:00:00Z'),
      run('valrun-002', 'user-other', '2026-02-21T11:00:00Z'),
      run('valrun-003', undefined, '2026-02-21T12:00:00Z'),
    ];
    const visible = filterRunsSharedWithMe(input, 'user-owner');
    visible[0] = {
      ...visible[0],
      permission: 'review',
      status: 'running',
      finalDecision: 'conditional_pass',
    };

    const filtered = filterSharedRunsForDisplay(visible, {
      ...DEFAULT_SHARED_RUN_LIST_FILTERS,
      query: '002',
      permission: 'review',
      status: 'running',
      decision: 'conditional_pass',
    });

    expect(filtered.map((item) => item.runId)).toEqual(['valrun-002']);
  });
});
