import { describe, expect, test } from 'bun:test';

import {
  applyValidationBotKeyRevocation,
  applyValidationBotKeyRotation,
  filterValidationBots,
  formatValidationBotTimestamp,
  mapValidationBotListResponse,
  mergeValidationBotSummary,
  normalizeValidationBotSummary,
  resolveValidationBotKeyStateCounts,
  resolveValidationBotRegistrationPathLabel,
  toValidationBotUsageLabel,
} from '../bot-ux-state';
import type {
  ValidationBotKeyMetadata,
  ValidationBotKeyMetadataResponse,
  ValidationBotKeyRotationResponse,
  ValidationBotRegistrationResponse,
  ValidationBotSummary,
} from '../types';

function makeKey(
  id: string,
  status: ValidationBotKeyMetadata['status'],
  createdAt: string,
): ValidationBotKeyMetadata {
  return {
    id,
    botId: 'bot-001',
    keyPrefix: `tnx.bot.${id}`,
    status,
    createdAt,
    lastUsedAt: null,
    revokedAt: status === 'revoked' ? createdAt : null,
  };
}

function makeBot(
  id: string,
  status: ValidationBotSummary['status'],
  createdAt: string,
  ownerUserId: string,
  keys: ValidationBotKeyMetadata[] = [],
): ValidationBotSummary {
  return normalizeValidationBotSummary({
    id,
    tenantId: 'tenant-001',
    ownerUserId,
    name: `Bot ${id}`,
    status,
    registrationPath: 'invite_code_trial',
    trialExpiresAt: null,
    metadata: { source: 'test' },
    createdAt,
    updatedAt: createdAt,
    keys,
    usage: {
      totalRequests: 0,
      lastSeenAt: null,
    },
  });
}

describe('bot ux state helpers', () => {
  test('mapValidationBotListResponse normalizes and sorts active-first deterministically', () => {
    const mapped = mapValidationBotListResponse({
      items: [
        makeBot('bot-revoked', 'revoked', '2026-02-20T10:00:00Z', 'user-3'),
        makeBot('bot-active-new', 'active', '2026-02-20T13:00:00Z', 'user-2', [
          makeKey('key-rotated', 'rotated', '2026-02-20T09:00:00Z'),
          makeKey('key-active', 'active', '2026-02-20T11:00:00Z'),
        ]),
        makeBot('bot-active-old', 'active', '2026-02-20T08:00:00Z', 'user-1'),
      ],
    });

    expect(mapped.map((bot) => bot.id)).toEqual([
      'bot-active-new',
      'bot-active-old',
      'bot-revoked',
    ]);
    expect(mapped[0]?.keys.map((key) => key.id)).toEqual(['key-active', 'key-rotated']);
  });

  test('mergeValidationBotSummary upserts bot and keeps deterministic ordering', () => {
    const current = [
      makeBot('bot-002', 'active', '2026-02-20T12:00:00Z', 'user-2'),
      makeBot('bot-001', 'active', '2026-02-20T10:00:00Z', 'user-1'),
    ];
    const registration: ValidationBotRegistrationResponse = {
      requestId: 'req-registration-001',
      bot: {
        id: 'bot-003',
        tenantId: 'tenant-001',
        ownerUserId: 'user-3',
        name: 'Bot bot-003',
        status: 'active',
        registrationPath: 'invite_code_trial',
        trialExpiresAt: null,
        metadata: { source: 'test' },
        createdAt: '2026-02-20T13:00:00Z',
        updatedAt: '2026-02-20T13:00:00Z',
      },
      registration: {
        id: 'reg-001',
        botId: 'bot-003',
        registrationPath: 'invite_code_trial',
        status: 'completed',
        createdAt: '2026-02-20T13:00:00Z',
      },
      issuedKey: {
        rawKey: 'tnx.bot.bot-003.key-001.secret',
        key: {
          id: 'key-001',
          botId: 'bot-003',
          keyPrefix: 'tnx.bot.key-001',
          status: 'active',
          createdAt: '2026-02-20T13:00:00Z',
        },
      },
    };

    const merged = mergeValidationBotSummary(current, registration);
    expect(merged.map((bot) => bot.id)).toEqual(['bot-003', 'bot-002', 'bot-001']);
    expect(merged[0]?.keys[0]?.id).toBe('key-001');
  });

  test('applyValidationBotKeyRotation marks previous active keys as rotated', () => {
    const current = [
      makeBot('bot-001', 'active', '2026-02-20T10:00:00Z', 'user-1', [
        makeKey('key-001', 'active', '2026-02-20T10:00:00Z'),
        makeKey('key-000', 'revoked', '2026-02-19T10:00:00Z'),
      ]),
    ];

    const rotation: ValidationBotKeyRotationResponse = {
      requestId: 'req-rotation-001',
      botId: 'bot-001',
      issuedKey: {
        rawKey: 'tnx.bot.bot-001.key-002.secret',
        key: {
          id: 'key-002',
          botId: 'bot-001',
          keyPrefix: 'tnx.bot.key-002',
          status: 'active',
          createdAt: '2026-02-20T12:00:00Z',
        },
      },
    };

    const updated = applyValidationBotKeyRotation(current, 'bot-001', rotation.issuedKey.key);
    expect(updated[0]?.keys.map((key) => `${key.id}:${key.status}`)).toEqual([
      'key-002:active',
      'key-001:rotated',
      'key-000:revoked',
    ]);
  });

  test('applyValidationBotKeyRevocation updates only the targeted key metadata', () => {
    const current = [
      makeBot('bot-001', 'active', '2026-02-20T10:00:00Z', 'user-1', [
        makeKey('key-001', 'active', '2026-02-20T10:00:00Z'),
        makeKey('key-002', 'rotated', '2026-02-20T09:00:00Z'),
      ]),
    ];
    const revoked: ValidationBotKeyMetadataResponse = {
      requestId: 'req-revoke-001',
      botId: 'bot-001',
      key: {
        id: 'key-001',
        botId: 'bot-001',
        keyPrefix: 'tnx.bot.key-001',
        status: 'revoked',
        createdAt: '2026-02-20T10:00:00Z',
        revokedAt: '2026-02-20T12:30:00Z',
      },
    };

    const updated = applyValidationBotKeyRevocation(current, 'bot-001', revoked.key);
    expect(updated[0]?.keys.find((key) => key.id === 'key-001')?.status).toBe('revoked');
    expect(updated[0]?.keys.find((key) => key.id === 'key-002')?.status).toBe('rotated');
  });

  test('filterValidationBots filters by lifecycle status and search terms', () => {
    const bots = [
      makeBot('bot-001', 'active', '2026-02-20T10:00:00Z', 'owner-alpha'),
      makeBot('bot-002', 'revoked', '2026-02-20T11:00:00Z', 'owner-beta'),
    ];

    expect(filterValidationBots(bots, 'revoked', '').map((bot) => bot.id)).toEqual(['bot-002']);
    expect(filterValidationBots(bots, 'all', 'owner-alpha').map((bot) => bot.id)).toEqual([
      'bot-001',
    ]);
  });

  test('resolveValidationBotKeyStateCounts returns lifecycle totals', () => {
    const bot = makeBot('bot-001', 'active', '2026-02-20T10:00:00Z', 'user-1', [
      makeKey('key-active', 'active', '2026-02-20T10:00:00Z'),
      makeKey('key-rotated', 'rotated', '2026-02-20T09:00:00Z'),
      makeKey('key-revoked', 'revoked', '2026-02-20T08:00:00Z'),
    ]);

    expect(resolveValidationBotKeyStateCounts(bot)).toEqual({
      active: 1,
      rotated: 1,
      revoked: 1,
    });
  });

  test('format and label helpers remain deterministic', () => {
    expect(formatValidationBotTimestamp('2026-02-20T13:14:15Z')).toBe('2026-02-20 13:14:15 UTC');
    expect(
      toValidationBotUsageLabel({ totalRequests: 1250, lastSeenAt: '2026-02-20T13:14:15Z' }),
    ).toBe('1,250 total requests, last seen 2026-02-20 13:14:15 UTC');
    expect(resolveValidationBotRegistrationPathLabel('invite_code_trial')).toBe(
      'Invite Code Trial',
    );
    expect(resolveValidationBotRegistrationPathLabel('partner_bootstrap')).toBe(
      'Partner Bootstrap',
    );
  });
});
