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
