import { sortValidationRunsByUpdatedAtDesc } from '@/lib/validation/review-run-list-state';
import type { ValidationRunSummary } from '@/lib/validation/types';

const REVIEW_RUN_HISTORY_STORAGE_KEY = 'trade-nexus.validation.review.run-history.v1';
const REVIEW_RUN_HISTORY_LIMIT = 50;

type RunHistoryStorage = Pick<Storage, 'getItem' | 'setItem'>;

function resolveStorage(candidate?: RunHistoryStorage | null): RunHistoryStorage | null {
  if (candidate) {
    return candidate;
  }
  if (typeof window === 'undefined') {
    return null;
  }
  return window.localStorage;
}

function toTimestamp(value: string): number {
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function isValidationRunSummary(value: unknown): value is ValidationRunSummary {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const run = value as Partial<ValidationRunSummary>;
  return (
    typeof run.id === 'string' &&
    typeof run.status === 'string' &&
    typeof run.profile === 'string' &&
    run.schemaVersion === 'validation-run.v1' &&
    typeof run.finalDecision === 'string' &&
    typeof run.createdAt === 'string' &&
    typeof run.updatedAt === 'string'
  );
}

function persistRunHistory(runs: ValidationRunSummary[], storage: RunHistoryStorage): void {
  storage.setItem(REVIEW_RUN_HISTORY_STORAGE_KEY, JSON.stringify(runs));
}

export function readReviewRunHistory(
  storageCandidate?: RunHistoryStorage | null,
): ValidationRunSummary[] {
  const storage = resolveStorage(storageCandidate);
  if (!storage) {
    return [];
  }

  const rawValue = storage.getItem(REVIEW_RUN_HISTORY_STORAGE_KEY);
  if (!rawValue) {
    return [];
  }

  try {
    const parsed = JSON.parse(rawValue) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }

    const deduplicated = new Map<string, ValidationRunSummary>();
    for (const item of parsed) {
      if (!isValidationRunSummary(item)) {
        continue;
      }
      const existing = deduplicated.get(item.id);
      if (!existing || toTimestamp(item.updatedAt) > toTimestamp(existing.updatedAt)) {
        deduplicated.set(item.id, item);
      }
    }
    return sortValidationRunsByUpdatedAtDesc(Array.from(deduplicated.values())).slice(
      0,
      REVIEW_RUN_HISTORY_LIMIT,
    );
  } catch {
    return [];
  }
}

export function upsertReviewRunHistory(
  run: ValidationRunSummary,
  storageCandidate?: RunHistoryStorage | null,
): ValidationRunSummary[] {
  const storage = resolveStorage(storageCandidate);
  const existing = readReviewRunHistory(storage);
  const deduplicated = [run, ...existing.filter((item) => item.id !== run.id)];
  const nextRuns = sortValidationRunsByUpdatedAtDesc(deduplicated).slice(
    0,
    REVIEW_RUN_HISTORY_LIMIT,
  );
  if (storage) {
    persistRunHistory(nextRuns, storage);
  }
  return nextRuns;
}
