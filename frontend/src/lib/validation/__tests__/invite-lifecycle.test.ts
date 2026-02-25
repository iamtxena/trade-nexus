import { describe, expect, test } from 'bun:test';

import {
  DEFAULT_INVITE_LIST_FILTERS,
  filterInvites,
  inviteActionLabel,
  markInviteRevoked,
  mergeInviteIntoList,
  summarizeInvitesByStatus,
} from '../invite-lifecycle';
import type { ValidationShareInvite } from '../types';

function invite(
  id: string,
  status: ValidationShareInvite['status'],
  createdAt: string,
): ValidationShareInvite {
  return {
    id,
    runId: 'valrun-001',
    email: `${id}@example.com`,
    permission: 'comment',
    status,
    invitedByUserId: 'user-1',
    invitedByActorType: 'user',
    createdAt,
    acceptedAt: null,
    revokedAt: null,
  };
}

describe('invite lifecycle helpers', () => {
  test('mergeInviteIntoList upserts and keeps newest-first ordering', () => {
    const base = [
      invite('inv-001', 'pending', '2026-02-20T10:00:00Z'),
      invite('inv-002', 'pending', '2026-02-20T12:00:00Z'),
    ];
    const merged = mergeInviteIntoList(base, invite('inv-003', 'pending', '2026-02-20T13:00:00Z'));
    expect(merged.map((item) => item.id)).toEqual(['inv-003', 'inv-002', 'inv-001']);
  });

  test('markInviteRevoked replaces only the targeted invite', () => {
    const base = [invite('inv-001', 'pending', '2026-02-20T10:00:00Z')];
    const revokedInvite: ValidationShareInvite = {
      ...invite('inv-001', 'revoked', '2026-02-20T10:00:00Z'),
      revokedAt: '2026-02-20T11:00:00Z',
    };
    const updated = markInviteRevoked(base, revokedInvite);
    expect(updated[0]?.status).toBe('revoked');
    expect(updated[0]?.revokedAt).toBe('2026-02-20T11:00:00Z');
  });

  test('inviteActionLabel distinguishes pending invite vs active shared access', () => {
    expect(inviteActionLabel(invite('inv-001', 'pending', '2026-02-20T10:00:00Z'))).toBe(
      'Revoke Invite',
    );
    expect(inviteActionLabel(invite('inv-002', 'accepted', '2026-02-20T10:00:00Z'))).toBe(
      'Revoke Access',
    );
  });

  test('filterInvites supports status, permission, and query filters', () => {
    const base = [
      invite('inv-001', 'pending', '2026-02-20T10:00:00Z'),
      { ...invite('inv-002', 'accepted', '2026-02-20T11:00:00Z'), permission: 'view' as const },
      { ...invite('inv-003', 'revoked', '2026-02-20T12:00:00Z'), permission: 'decide' as const },
    ];

    const filtered = filterInvites(base, {
      ...DEFAULT_INVITE_LIST_FILTERS,
      status: 'accepted',
      permission: 'view',
      query: 'inv-002',
    });

    expect(filtered.map((item) => item.id)).toEqual(['inv-002']);
  });

  test('summarizeInvitesByStatus returns full status counts', () => {
    const base = [
      invite('inv-001', 'pending', '2026-02-20T10:00:00Z'),
      invite('inv-002', 'pending', '2026-02-20T11:00:00Z'),
      invite('inv-003', 'accepted', '2026-02-20T12:00:00Z'),
      invite('inv-004', 'expired', '2026-02-20T13:00:00Z'),
      invite('inv-005', 'revoked', '2026-02-20T14:00:00Z'),
    ];

    expect(summarizeInvitesByStatus(base)).toEqual({
      pending: 2,
      accepted: 1,
      revoked: 1,
      expired: 1,
    });
  });
});
