import type { ValidationSharedRunSummary } from '@/lib/validation/types';

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
