const DEFAULT_SIGN_IN_REDIRECT_URL = '/dashboard';

function toSingleValue(value: string | string[] | null | undefined): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}

function toInAppPath(value: string): string | null {
  if (value.startsWith('/')) {
    return value;
  }

  try {
    const parsed = new URL(value);
    const path = `${parsed.pathname}${parsed.search}${parsed.hash}`;
    return path.startsWith('/') ? path : null;
  } catch {
    return null;
  }
}

export function resolveSignInForceRedirectUrl(
  redirectUrlParam: string | string[] | null | undefined,
): string {
  const candidate = toSingleValue(redirectUrlParam)?.trim();
  if (!candidate) {
    return DEFAULT_SIGN_IN_REDIRECT_URL;
  }

  return toInAppPath(candidate) ?? DEFAULT_SIGN_IN_REDIRECT_URL;
}
