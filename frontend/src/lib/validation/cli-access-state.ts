import type {
  ValidationCliSession,
  ValidationCliSessionListResponse,
} from '@/lib/validation/types';

export interface ValidationCliPendingDeviceRequest {
  userCode: string;
  requestedAt: string;
}

export interface ValidationCliPendingApprovalRow extends ValidationCliPendingDeviceRequest {
  showApproveAction: true;
}

export interface ValidationCliUserCodeImportResolution {
  normalizedUserCode: string | null;
  nextImportedKey: string | null;
  shouldQueue: boolean;
}

type CliAccessStorage = Pick<Storage, 'getItem' | 'setItem'>;

const CLI_PENDING_REQUEST_KEY_PREFIX = 'trade-nexus.validation.cli-access.pending.v1';
const CLI_PENDING_REQUEST_LIMIT = 50;
const CLI_USER_CODE_PATTERN = /^[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$/;

function resolveStorage(candidate?: CliAccessStorage | null): CliAccessStorage | null {
  if (candidate) {
    return candidate;
  }
  if (typeof window === 'undefined') {
    return null;
  }
  return window.localStorage;
}

function toTimestamp(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function normalizeOwnerScope(ownerScope: string | null | undefined): string {
  const normalized = ownerScope?.trim().toLowerCase();
  if (!normalized) {
    return 'anonymous';
  }
  return normalized;
}

function pendingStorageKey(ownerScope: string | null | undefined): string {
  return `${CLI_PENDING_REQUEST_KEY_PREFIX}:${normalizeOwnerScope(ownerScope)}`;
}

function importedUserCodeKey(ownerScope: string | null | undefined, userCode: string): string {
  return `${normalizeOwnerScope(ownerScope)}:${userCode}`;
}

function isPendingRequest(value: unknown): value is ValidationCliPendingDeviceRequest {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const record = value as Partial<ValidationCliPendingDeviceRequest>;
  return typeof record.userCode === 'string' && typeof record.requestedAt === 'string';
}

function persistPendingRequests(
  ownerScope: string | null | undefined,
  requests: ValidationCliPendingDeviceRequest[],
  storage: CliAccessStorage,
): void {
  storage.setItem(pendingStorageKey(ownerScope), JSON.stringify(requests));
}

export function normalizeValidationCliUserCode(value: string): string | null {
  const compact = value.toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (compact.length !== 8) {
    return null;
  }
  const normalized = `${compact.slice(0, 4)}-${compact.slice(4)}`;
  if (!CLI_USER_CODE_PATTERN.test(normalized)) {
    return null;
  }
  return normalized;
}

export function formatValidationCliTimestamp(value: string | null | undefined): string {
  if (!value) {
    return 'Unknown';
  }
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return 'Unknown';
  }
  const iso = new Date(parsed).toISOString();
  return `${iso.slice(0, 19).replace('T', ' ')} UTC`;
}

export function resolveValidationCliUserCodeImport(params: {
  ownerScope: string | null | undefined;
  urlUserCode: string | null | undefined;
  previousImportedKey: string | null;
}): ValidationCliUserCodeImportResolution {
  const { ownerScope, urlUserCode, previousImportedKey } = params;
  if (!urlUserCode) {
    return {
      normalizedUserCode: null,
      nextImportedKey: null,
      shouldQueue: false,
    };
  }

  const normalizedUserCode = normalizeValidationCliUserCode(urlUserCode);
  if (!normalizedUserCode) {
    return {
      normalizedUserCode: null,
      nextImportedKey: previousImportedKey,
      shouldQueue: false,
    };
  }

  const nextImportedKey = importedUserCodeKey(ownerScope, normalizedUserCode);
  if (nextImportedKey === previousImportedKey) {
    return {
      normalizedUserCode,
      nextImportedKey: previousImportedKey,
      shouldQueue: false,
    };
  }

  return {
    normalizedUserCode,
    nextImportedKey,
    shouldQueue: true,
  };
}

export function mapValidationCliSessionListResponse(payload: unknown): ValidationCliSession[] {
  if (!payload || typeof payload !== 'object') {
    return [];
  }
  const response = payload as Partial<ValidationCliSessionListResponse>;
  if (!Array.isArray(response.sessions)) {
    return [];
  }
  return [...response.sessions].sort(
    (left, right) => toTimestamp(right.createdAt) - toTimestamp(left.createdAt),
  );
}

export function buildValidationCliPendingApprovalRows(
  requests: ValidationCliPendingDeviceRequest[],
): ValidationCliPendingApprovalRow[] {
  return [...requests]
    .sort((left, right) => toTimestamp(right.requestedAt) - toTimestamp(left.requestedAt))
    .map((request) => ({
      ...request,
      showApproveAction: true,
    }));
}

export function readPendingCliDeviceRequests(
  ownerScope: string | null | undefined,
  storageCandidate?: CliAccessStorage | null,
): ValidationCliPendingDeviceRequest[] {
  const storage = resolveStorage(storageCandidate);
  if (!storage) {
    return [];
  }
  const rawValue = storage.getItem(pendingStorageKey(ownerScope));
  if (!rawValue) {
    return [];
  }

  try {
    const parsed = JSON.parse(rawValue) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }
    const deduplicated = new Map<string, ValidationCliPendingDeviceRequest>();
    for (const item of parsed) {
      if (!isPendingRequest(item)) {
        continue;
      }
      const normalizedUserCode = normalizeValidationCliUserCode(item.userCode);
      if (!normalizedUserCode) {
        continue;
      }
      const existing = deduplicated.get(normalizedUserCode);
      if (!existing || toTimestamp(item.requestedAt) > toTimestamp(existing.requestedAt)) {
        deduplicated.set(normalizedUserCode, {
          userCode: normalizedUserCode,
          requestedAt: item.requestedAt,
        });
      }
    }
    return Array.from(deduplicated.values())
      .sort((left, right) => toTimestamp(right.requestedAt) - toTimestamp(left.requestedAt))
      .slice(0, CLI_PENDING_REQUEST_LIMIT);
  } catch {
    return [];
  }
}

export function upsertPendingCliDeviceRequest(
  ownerScope: string | null | undefined,
  userCode: string,
  storageCandidate?: CliAccessStorage | null,
): ValidationCliPendingDeviceRequest[] {
  const normalizedUserCode = normalizeValidationCliUserCode(userCode);
  if (!normalizedUserCode) {
    return readPendingCliDeviceRequests(ownerScope, storageCandidate);
  }

  const storage = resolveStorage(storageCandidate);
  const existing = readPendingCliDeviceRequests(ownerScope, storage);
  const next = [
    {
      userCode: normalizedUserCode,
      requestedAt: new Date().toISOString(),
    },
    ...existing.filter((item) => item.userCode !== normalizedUserCode),
  ].slice(0, CLI_PENDING_REQUEST_LIMIT);

  if (storage) {
    persistPendingRequests(ownerScope, next, storage);
  }
  return next;
}

export function removePendingCliDeviceRequest(
  ownerScope: string | null | undefined,
  userCode: string,
  storageCandidate?: CliAccessStorage | null,
): ValidationCliPendingDeviceRequest[] {
  const normalizedUserCode = normalizeValidationCliUserCode(userCode);
  if (!normalizedUserCode) {
    return readPendingCliDeviceRequests(ownerScope, storageCandidate);
  }

  const storage = resolveStorage(storageCandidate);
  const next = readPendingCliDeviceRequests(ownerScope, storage).filter(
    (item) => item.userCode !== normalizedUserCode,
  );
  if (storage) {
    persistPendingRequests(ownerScope, next, storage);
  }
  return next;
}
