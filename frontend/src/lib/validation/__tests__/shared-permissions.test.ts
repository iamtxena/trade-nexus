import { describe, expect, test } from 'bun:test';

import {
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
});
