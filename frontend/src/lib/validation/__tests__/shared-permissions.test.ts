import { describe, expect, test } from 'bun:test';

import {
  describeSharedValidationPermission,
  hasSharedValidationPermission,
  resolveSharedValidationCapabilities,
} from '../shared-permissions';

describe('shared validation permissions', () => {
  test('view permission is read-only', () => {
    const capabilities = resolveSharedValidationCapabilities('view');
    expect(capabilities.canView).toBe(true);
    expect(capabilities.canComment).toBe(false);
    expect(capabilities.canDecide).toBe(false);
  });

  test('comment permission allows comments but blocks decisions', () => {
    const capabilities = resolveSharedValidationCapabilities('comment');
    expect(capabilities.canView).toBe(true);
    expect(capabilities.canComment).toBe(true);
    expect(capabilities.canDecide).toBe(false);
  });

  test('decide permission includes all actions', () => {
    expect(hasSharedValidationPermission('decide', 'view')).toBe(true);
    expect(hasSharedValidationPermission('decide', 'comment')).toBe(true);
    expect(hasSharedValidationPermission('decide', 'decide')).toBe(true);
  });

  test('describeSharedValidationPermission exposes clear UI metadata', () => {
    const viewDescriptor = describeSharedValidationPermission('view');
    expect(viewDescriptor.label).toBe('View only');
    expect(viewDescriptor.summary).toContain('inspect artifact');
    expect(viewDescriptor.canComment).toBe(false);

    const decideDescriptor = describeSharedValidationPermission('decide');
    expect(decideDescriptor.label).toBe('Decide');
    expect(decideDescriptor.canView).toBe(true);
    expect(decideDescriptor.canComment).toBe(true);
    expect(decideDescriptor.canDecide).toBe(true);
  });
});
