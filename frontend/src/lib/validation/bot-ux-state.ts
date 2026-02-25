import type {
  ValidationBotKeyMetadata,
  ValidationBotKeyStatus,
  ValidationBotRegistrationPath,
  ValidationBotRegistrationResponse,
  ValidationBotStatus,
  ValidationBotSummary,
  ValidationBotUsageMetadata,
} from '@/lib/validation/types';

const BOT_STATUS_WEIGHT: Record<ValidationBotStatus, number> = {
  active: 0,
  suspended: 1,
  revoked: 2,
};

const KEY_STATUS_WEIGHT: Record<ValidationBotKeyStatus, number> = {
  active: 0,
  rotated: 1,
  revoked: 2,
};

const REQUEST_COUNT_FORMATTER = new Intl.NumberFormat('en-US');

function toTimestamp(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function sortValidationBotKeys(keys: ValidationBotKeyMetadata[]): ValidationBotKeyMetadata[] {
  return [...keys].sort((left, right) => {
    const statusDelta = KEY_STATUS_WEIGHT[left.status] - KEY_STATUS_WEIGHT[right.status];
    if (statusDelta !== 0) {
      return statusDelta;
    }

    const createdAtDelta = toTimestamp(right.createdAt) - toTimestamp(left.createdAt);
    if (createdAtDelta !== 0) {
      return createdAtDelta;
    }

    return left.id.localeCompare(right.id);
  });
}

export function normalizeValidationBotSummary(bot: ValidationBotSummary): ValidationBotSummary {
  return {
    ...bot,
    keys: sortValidationBotKeys(bot.keys ?? []),
  };
}

export function sortValidationBotSummaries(bots: ValidationBotSummary[]): ValidationBotSummary[] {
  return [...bots].sort((left, right) => {
    const statusDelta = BOT_STATUS_WEIGHT[left.status] - BOT_STATUS_WEIGHT[right.status];
    if (statusDelta !== 0) {
      return statusDelta;
    }

    const createdAtDelta = toTimestamp(right.createdAt) - toTimestamp(left.createdAt);
    if (createdAtDelta !== 0) {
      return createdAtDelta;
    }

    return left.id.localeCompare(right.id);
  });
}

export function mapValidationBotListResponse(payload: unknown): ValidationBotSummary[] {
  if (!payload || typeof payload !== 'object') {
    return [];
  }

  const value = payload as { bots?: ValidationBotSummary[]; items?: ValidationBotSummary[] };
  const entries = Array.isArray(value.bots)
    ? value.bots
    : Array.isArray(value.items)
      ? value.items
      : [];

  return sortValidationBotSummaries(entries.map(normalizeValidationBotSummary));
}

export function mergeValidationBotSummary(
  current: ValidationBotSummary[],
  registration: ValidationBotRegistrationResponse,
): ValidationBotSummary[] {
  const incoming: ValidationBotSummary = normalizeValidationBotSummary({
    ...registration.bot,
    keys: [registration.issuedKey.key],
  });
  const filtered = current.filter((bot) => bot.id !== incoming.id);
  return sortValidationBotSummaries([incoming, ...filtered]);
}

export function applyValidationBotKeyRotation(
  current: ValidationBotSummary[],
  botId: string,
  issuedKey: ValidationBotKeyMetadata,
): ValidationBotSummary[] {
  const updated = current.map((bot) => {
    if (bot.id !== botId) {
      return bot;
    }
    const normalizedExisting = bot.keys.map((key) =>
      key.status === 'active' ? { ...key, status: 'rotated' as const } : key,
    );
    return normalizeValidationBotSummary({
      ...bot,
      keys: [issuedKey, ...normalizedExisting],
    });
  });

  return sortValidationBotSummaries(updated);
}

export function applyValidationBotKeyRevocation(
  current: ValidationBotSummary[],
  botId: string,
  revokedKey: ValidationBotKeyMetadata,
): ValidationBotSummary[] {
  const updated = current.map((bot) => {
    if (bot.id !== botId) {
      return bot;
    }
    return normalizeValidationBotSummary({
      ...bot,
      keys: bot.keys.map((key) => (key.id === revokedKey.id ? revokedKey : key)),
    });
  });

  return sortValidationBotSummaries(updated);
}

export interface ValidationBotKeyStateCounts {
  active: number;
  rotated: number;
  revoked: number;
}

export function resolveValidationBotKeyStateCounts(
  bot: Pick<ValidationBotSummary, 'keys'>,
): ValidationBotKeyStateCounts {
  const totals: ValidationBotKeyStateCounts = { active: 0, rotated: 0, revoked: 0 };
  for (const key of bot.keys) {
    if (key.status === 'active') {
      totals.active += 1;
      continue;
    }
    if (key.status === 'rotated') {
      totals.rotated += 1;
      continue;
    }
    totals.revoked += 1;
  }
  return totals;
}

export type ValidationBotListFilter = 'all' | ValidationBotStatus;

export function filterValidationBots(
  bots: ValidationBotSummary[],
  filter: ValidationBotListFilter,
  query: string,
): ValidationBotSummary[] {
  const normalizedQuery = query.trim().toLowerCase();

  return bots.filter((bot) => {
    if (filter !== 'all' && bot.status !== filter) {
      return false;
    }
    if (!normalizedQuery) {
      return true;
    }

    const searchable = [
      bot.name,
      bot.id,
      bot.ownerUserId,
      bot.registrationPath,
      ...bot.keys.map((key) => key.keyPrefix),
    ]
      .join(' ')
      .toLowerCase();

    return searchable.includes(normalizedQuery);
  });
}

export function resolveValidationBotOwnershipLabel(
  bot: Pick<ValidationBotSummary, 'ownerUserId'>,
): string {
  return bot.ownerUserId?.trim() ? bot.ownerUserId : 'owner-unavailable';
}

export function resolveValidationBotRegistrationPathLabel(
  registrationPath: ValidationBotRegistrationPath,
): string {
  if (registrationPath === 'invite_code_trial') {
    return 'Invite Code Trial';
  }
  return 'Partner Bootstrap';
}

export function formatValidationBotTimestamp(value: string | null | undefined): string {
  if (!value) {
    return 'Unknown';
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return 'Unknown';
  }
  const iso = new Date(timestamp).toISOString();
  return `${iso.slice(0, 19).replace('T', ' ')} UTC`;
}

export function toValidationBotUsageLabel(usage: ValidationBotUsageMetadata | undefined): string {
  if (!usage) {
    return 'No usage telemetry yet';
  }

  const requests =
    usage.totalRequests !== undefined
      ? `${REQUEST_COUNT_FORMATTER.format(usage.totalRequests)} total requests`
      : '';
  const lastSeen = usage.lastSeenAt
    ? `last seen ${formatValidationBotTimestamp(usage.lastSeenAt)}`
    : 'never used';
  return requests ? `${requests}, ${lastSeen}` : lastSeen;
}
