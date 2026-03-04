import { describe, expect, test } from 'bun:test';

import { resolveSignInForceRedirectUrl } from '../sign-in-redirect';

describe('resolveSignInForceRedirectUrl', () => {
  test('preserves cli access user_code from relative redirect url', () => {
    expect(resolveSignInForceRedirectUrl('/cli-access?user_code=ABCD-2345')).toBe(
      '/cli-access?user_code=ABCD-2345',
    );
  });

  test('preserves cli access user_code from absolute redirect url', () => {
    expect(
      resolveSignInForceRedirectUrl('https://app.local/cli-access?user_code=ABCD-2345'),
    ).toBe('/cli-access?user_code=ABCD-2345');
  });

  test('falls back to dashboard for missing or invalid redirect url', () => {
    expect(resolveSignInForceRedirectUrl(null)).toBe('/dashboard');
    expect(resolveSignInForceRedirectUrl('not-a-valid-url')).toBe('/dashboard');
  });
});
