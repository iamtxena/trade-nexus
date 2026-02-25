import type { ValidationSharePermission } from '@/lib/validation/types';

const PERMISSION_RANK: Record<ValidationSharePermission, number> = {
  view: 0,
  comment: 1,
  decide: 2,
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
  comment: {
    label: 'Comment',
    summary: 'Includes view access and can submit review comments.',
  },
  decide: {
    label: 'Decide',
    summary: 'Includes comment access and can submit final decisions.',
  },
};

export function hasSharedValidationPermission(
  permission: ValidationSharePermission,
  required: ValidationSharePermission,
): boolean {
  return PERMISSION_RANK[permission] >= PERMISSION_RANK[required];
}

export function resolveSharedValidationCapabilities(
  permission: ValidationSharePermission,
): SharedValidationCapabilities {
  return {
    canView: hasSharedValidationPermission(permission, 'view'),
    canComment: hasSharedValidationPermission(permission, 'comment'),
    canDecide: hasSharedValidationPermission(permission, 'decide'),
  };
}

export function describeSharedValidationPermission(
  permission: ValidationSharePermission,
): SharedValidationPermissionDescriptor {
  return {
    permission,
    ...SHARED_PERMISSION_METADATA[permission],
    ...resolveSharedValidationCapabilities(permission),
  };
}
