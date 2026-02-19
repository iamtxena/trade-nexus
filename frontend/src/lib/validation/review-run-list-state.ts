import type { ValidationRunSummary } from '@/lib/validation/types';

function toTimestamp(value: string): number {
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

export function sortValidationRunsByUpdatedAtDesc(
  runs: ValidationRunSummary[],
): ValidationRunSummary[] {
  return [...runs].sort(
    (left, right) => toTimestamp(right.updatedAt) - toTimestamp(left.updatedAt),
  );
}

export function resolveRunIdForListToDetailTransition(
  runs: ValidationRunSummary[],
  explicitRunId: string | null,
  activeRunId: string | null,
): string | null {
  const runIds = new Set(runs.map((run) => run.id));
  if (explicitRunId && runIds.has(explicitRunId)) {
    return explicitRunId;
  }
  if (activeRunId && runIds.has(activeRunId)) {
    return activeRunId;
  }
  return runs.length > 0 ? (runs[0]?.id ?? null) : null;
}
