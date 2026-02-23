import { describe, expect, test } from 'bun:test';

import { isPathProtected } from '../protected-routes';

describe('isPathProtected', () => {
  test('protects owner and shared validation surfaces', () => {
    expect(isPathProtected('/validation')).toBe(true);
    expect(isPathProtected('/validation/run-1')).toBe(true);
    expect(isPathProtected('/shared-validation')).toBe(true);
    expect(isPathProtected('/shared-validation/valrun-123')).toBe(true);
  });

  test('protects bots pages and related API routes', () => {
    expect(isPathProtected('/bots')).toBe(true);
    expect(isPathProtected('/api/validation/bots')).toBe(true);
    expect(isPathProtected('/api/shared-validation/runs')).toBe(true);
  });

  test('does not protect public pages', () => {
    expect(isPathProtected('/')).toBe(false);
    expect(isPathProtected('/sign-in')).toBe(false);
    expect(isPathProtected('/docs')).toBe(false);
  });
});
