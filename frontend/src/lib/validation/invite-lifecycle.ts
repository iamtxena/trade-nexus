import type { ValidationShareInvite } from '@/lib/validation/types';

function toTimestamp(value: string): number {
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function sortInvitesByCreatedAtDesc(invites: ValidationShareInvite[]): ValidationShareInvite[] {
  return [...invites].sort(
    (left, right) => toTimestamp(right.createdAt) - toTimestamp(left.createdAt),
  );
}

export function mergeInviteIntoList(
  invites: ValidationShareInvite[],
  incoming: ValidationShareInvite,
): ValidationShareInvite[] {
  const withoutIncoming = invites.filter((invite) => invite.id !== incoming.id);
  return sortInvitesByCreatedAtDesc([incoming, ...withoutIncoming]);
}

export function markInviteRevoked(
  invites: ValidationShareInvite[],
  incoming: ValidationShareInvite,
): ValidationShareInvite[] {
  return invites.map((invite) => (invite.id === incoming.id ? incoming : invite));
}

export function inviteActionLabel(invite: ValidationShareInvite): string {
  return invite.status === 'accepted' ? 'Revoke Access' : 'Revoke Invite';
}
