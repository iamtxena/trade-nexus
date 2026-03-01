import { describe, expect, test } from 'bun:test';

import {
  describeSharedValidationPermission,
  hasSharedValidationPermission,
  normalizeSharedValidationPermission,
  resolveSharedValidationCapabilities,
} from '../shared-permissions';

describe('shared validation permissions', () => {
  test('view permission is read-only', () => {
    const capabilities = resolveSharedValidationCapabilities('view');
    expect(capabilities.canView).toBe(true);
    expect(capabilities.canComment).toBe(false);
    expect(capabilities.canDecide).toBe(false);
  });

  test('review permission allows comments and decisions', () => {
    const capabilities = resolveSharedValidationCapabilities('review');
    expect(capabilities.canView).toBe(true);
    expect(capabilities.canComment).toBe(true);
    expect(capabilities.canDecide).toBe(true);
  });

  test('legacy aliases normalize deterministically to review', () => {
    expect(normalizeSharedValidationPermission('comment')).toBe('review');
    expect(normalizeSharedValidationPermission('decide')).toBe('review');
    expect(normalizeSharedValidationPermission('unknown')).toBe('view');

    expect(resolveSharedValidationCapabilities('comment')).toEqual(
      resolveSharedValidationCapabilities('review'),
    );
    expect(resolveSharedValidationCapabilities('decide')).toEqual(
      resolveSharedValidationCapabilities('review'),
    );
  });

  test('review access includes all reviewer actions', () => {
    expect(hasSharedValidationPermission('review', 'view')).toBe(true);
    expect(hasSharedValidationPermission('review', 'review')).toBe(true);
    expect(hasSharedValidationPermission('view', 'review')).toBe(false);
    expect(hasSharedValidationPermission('comment', 'review')).toBe(true);
    expect(hasSharedValidationPermission('decide', 'review')).toBe(true);
  });

  test('describeSharedValidationPermission exposes clear UI metadata', () => {
    const viewDescriptor = describeSharedValidationPermission('view');
    expect(viewDescriptor.label).toBe('View only');
    expect(viewDescriptor.summary).toContain('inspect artifact');
    expect(viewDescriptor.canComment).toBe(false);

    const reviewDescriptor = describeSharedValidationPermission('review');
    expect(reviewDescriptor.permission).toBe('review');
    expect(reviewDescriptor.label).toBe('Review');
    expect(reviewDescriptor.canView).toBe(true);
    expect(reviewDescriptor.canComment).toBe(true);
    expect(reviewDescriptor.canDecide).toBe(true);

    const legacyDescriptor = describeSharedValidationPermission('decide');
    expect(legacyDescriptor.permission).toBe('review');
    expect(legacyDescriptor.label).toBe('Review');
  });
});
