import type { ValidationSharePermission } from '@/lib/validation/types';

const LEGACY_SHARED_PERMISSION_ALIASES = {
  comment: 'review',
  decide: 'review',
} as const;

export type LegacyValidationSharePermissionAlias = keyof typeof LEGACY_SHARED_PERMISSION_ALIASES;
export type SharedValidationPermissionLike =
  | ValidationSharePermission
  | LegacyValidationSharePermissionAlias;

const PERMISSION_RANK: Record<ValidationSharePermission, number> = {
  view: 0,
  review: 1,
};

export interface SharedValidationCapabilities {
  canView: boolean;
  canComment: boolean;
  canDecide: boolean;
}

interface SharedPermissionMetadata {
  label: string;
  summary: string;
}

export interface SharedValidationPermissionDescriptor
  extends SharedValidationCapabilities,
    SharedPermissionMetadata {
  permission: ValidationSharePermission;
}

const SHARED_PERMISSION_METADATA: Record<ValidationSharePermission, SharedPermissionMetadata> = {
  view: {
    label: 'View only',
    summary: 'Can open the run and inspect artifact data.',
  },
  review: {
    label: 'Review',
    summary: 'Includes view access and can submit review comments and decisions.',
  },
};

export function normalizeSharedValidationPermission(
  permission: SharedValidationPermissionLike | string | null | undefined,
  fallback: ValidationSharePermission = 'view',
): ValidationSharePermission {
  if (permission === 'view' || permission === 'review') {
    return permission;
  }
  if (permission === 'comment' || permission === 'decide') {
    return LEGACY_SHARED_PERMISSION_ALIASES[permission];
  }
  return fallback;
}

export function hasSharedValidationPermission(
  permission: SharedValidationPermissionLike,
  required: SharedValidationPermissionLike,
): boolean {
  const normalizedPermission = normalizeSharedValidationPermission(permission);
  const normalizedRequiredPermission = normalizeSharedValidationPermission(required);
  return PERMISSION_RANK[normalizedPermission] >= PERMISSION_RANK[normalizedRequiredPermission];
}

export function resolveSharedValidationCapabilities(
  permission: SharedValidationPermissionLike,
): SharedValidationCapabilities {
  const normalizedPermission = normalizeSharedValidationPermission(permission);
  return {
    canView: hasSharedValidationPermission(normalizedPermission, 'view'),
    canComment: hasSharedValidationPermission(normalizedPermission, 'review'),
    canDecide: hasSharedValidationPermission(normalizedPermission, 'review'),
  };
}

export function describeSharedValidationPermission(
  permission: SharedValidationPermissionLike,
): SharedValidationPermissionDescriptor {
  const normalizedPermission = normalizeSharedValidationPermission(permission);
  return {
    permission: normalizedPermission,
    ...SHARED_PERMISSION_METADATA[normalizedPermission],
    ...resolveSharedValidationCapabilities(normalizedPermission),
  };
}
