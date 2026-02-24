const DEFAULT_VALIDATION_SMOKE_API_KEY = 'tnx.bot.validation-proxy-smoke';
const VALIDATION_SMOKE_SHARED_KEY_ENV = 'VALIDATION_PROXY_SMOKE_SHARED_KEY';

function nonEmpty(value: string | null | undefined): string | null {
  if (typeof value !== 'string') {
    return null;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

function readConfiguredSmokeSharedKey(): string | null {
  return nonEmpty(process.env[VALIDATION_SMOKE_SHARED_KEY_ENV]);
}

function normalizeRuntimeBotApiKey(candidate: string | null): string {
  if (candidate?.startsWith('tnx.bot.')) {
    return candidate;
  }
  return DEFAULT_VALIDATION_SMOKE_API_KEY;
}

export function hasValidValidationSmokeSharedKey(headers: Pick<Headers, 'get'>): boolean {
  const configured = readConfiguredSmokeSharedKey();
  if (!configured) {
    return false;
  }
  const provided = nonEmpty(headers.get('x-validation-smoke-key'));
  if (!provided) {
    return false;
  }
  return provided === configured;
}

export function resolveValidationSmokeApiKey(headers: Pick<Headers, 'get'>): string | null {
  if (!hasValidValidationSmokeSharedKey(headers)) {
    return null;
  }
  const providedApiKey = nonEmpty(headers.get('x-api-key'));
  return normalizeRuntimeBotApiKey(providedApiKey);
}
