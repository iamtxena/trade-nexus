import type {
  ValidationInviteStatus,
  ValidationShareInvite,
  ValidationSharePermission,
} from '@/lib/validation/types';

export type InviteStatusFilter = ValidationInviteStatus | 'all';
export type InvitePermissionFilter = ValidationSharePermission | 'all';

export interface InviteListFilters {
  query: string;
  status: InviteStatusFilter;
  permission: InvitePermissionFilter;
}

export const DEFAULT_INVITE_LIST_FILTERS = {
  query: '',
  status: 'all',
  permission: 'all',
} as const satisfies InviteListFilters;

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

export function filterInvites(
  invites: ValidationShareInvite[],
  filters: InviteListFilters,
): ValidationShareInvite[] {
  const query = filters.query.trim().toLowerCase();
  return invites.filter((invite) => {
    if (filters.status !== 'all' && invite.status !== filters.status) {
      return false;
    }
    if (filters.permission !== 'all' && invite.permission !== filters.permission) {
      return false;
    }
    if (query.length > 0) {
      return invite.email.toLowerCase().includes(query) || invite.id.toLowerCase().includes(query);
    }
    return true;
  });
}

export function summarizeInvitesByStatus(
  invites: ValidationShareInvite[],
): Record<ValidationInviteStatus, number> {
  const summary: Record<ValidationInviteStatus, number> = {
    pending: 0,
    accepted: 0,
    revoked: 0,
    expired: 0,
  };

  for (const invite of invites) {
    summary[invite.status] += 1;
  }

  return summary;
}
