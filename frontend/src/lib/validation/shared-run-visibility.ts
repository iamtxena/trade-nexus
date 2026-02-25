import type {
  ValidationDecision,
  ValidationRunStatus,
  ValidationSharePermission,
  ValidationSharedRunSummary,
} from '@/lib/validation/types';

export type SharedRunPermissionFilter = ValidationSharePermission | 'all';
export type SharedRunStatusFilter = ValidationRunStatus | 'all';
export type SharedRunDecisionFilter = ValidationDecision | 'all';

export interface SharedRunListFilters {
  query: string;
  permission: SharedRunPermissionFilter;
  status: SharedRunStatusFilter;
  decision: SharedRunDecisionFilter;
}

export const DEFAULT_SHARED_RUN_LIST_FILTERS = {
  query: '',
  permission: 'all',
  status: 'all',
  decision: 'all',
} as const satisfies SharedRunListFilters;

export function filterRunsSharedWithMe(
  runs: ValidationSharedRunSummary[],
  currentUserId: string,
): ValidationSharedRunSummary[] {
  return runs.filter((run) => {
    if (!run.ownerUserId) {
      return true;
    }
    return run.ownerUserId !== currentUserId;
  });
}

export function filterSharedRunsForDisplay(
  runs: ValidationSharedRunSummary[],
  filters: SharedRunListFilters,
): ValidationSharedRunSummary[] {
  const query = filters.query.trim().toLowerCase();

  return runs.filter((run) => {
    if (filters.permission !== 'all' && run.permission !== filters.permission) {
      return false;
    }
    if (filters.status !== 'all' && run.status !== filters.status) {
      return false;
    }
    if (filters.decision !== 'all' && run.finalDecision !== filters.decision) {
      return false;
    }
    if (query.length > 0) {
      return run.runId.toLowerCase().includes(query);
    }
    return true;
  });
}
