import { existsSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

export const LONA_GATEWAY_URL = process.env.LONA_GATEWAY_URL ?? 'https://gateway.lona.agency';
export const LIVE_ENGINE_URL = process.env.LIVE_ENGINE_URL ?? 'https://live.lona.agency';
export const LIVE_ENGINE_SERVICE_KEY = process.env.LIVE_ENGINE_SERVICE_KEY ?? '';

type LonaCredentialsFile = {
  lona_token?: string;
  token?: string;
  api_key?: string;
  lona_api_key?: string;
  agent_id?: string;
  user_id?: string;
  lona_user_id?: string;
};

let lonaCredentialsInitialized = false;

function firstNonEmpty(...values: Array<string | undefined>): string | undefined {
  for (const value of values) {
    const normalized = value?.trim();
    if (normalized) return normalized;
  }
  return undefined;
}

function applyAliasEnvFallbacks(): void {
  if (!process.env.LONA_AGENT_TOKEN) {
    const token = firstNonEmpty(process.env.LONA_API_KEY, process.env.LONA_TOKEN);
    if (token) process.env.LONA_AGENT_TOKEN = token;
  }

  if (!process.env.LONA_AGENT_ID) {
    const userId = firstNonEmpty(process.env.LONA_USER_ID);
    if (userId) process.env.LONA_AGENT_ID = userId;
  }
}

function applyCredentialsFileFallbacks(): void {
  if (process.env.LONA_AGENT_TOKEN && process.env.LONA_AGENT_ID) return;

  const credentialsPath =
    firstNonEmpty(process.env.LONA_CREDENTIALS_FILE) ?? join(homedir(), '.lona-credentials.json');

  if (!existsSync(credentialsPath)) return;

  try {
    const parsed = JSON.parse(readFileSync(credentialsPath, 'utf-8')) as LonaCredentialsFile;

    if (!process.env.LONA_AGENT_TOKEN) {
      const token = firstNonEmpty(
        parsed.lona_token,
        parsed.token,
        parsed.api_key,
        parsed.lona_api_key,
      );
      if (token) process.env.LONA_AGENT_TOKEN = token;
    }

    if (!process.env.LONA_AGENT_ID) {
      const userId = firstNonEmpty(parsed.agent_id, parsed.user_id, parsed.lona_user_id);
      if (userId) process.env.LONA_AGENT_ID = userId;
    }
  } catch {
    // Intentionally ignore invalid JSON/read errors and fall back to env defaults.
  }
}

export function initializeLonaCredentials(options?: { force?: boolean }): void {
  if (lonaCredentialsInitialized && !options?.force) return;

  lonaCredentialsInitialized = true;

  // 1) Normalize legacy env names used by MCP/older clients
  applyAliasEnvFallbacks();
  // 2) Load from shared credentials file if canonical vars are still missing
  applyCredentialsFileFallbacks();
  // 3) Re-apply alias normalization after file load
  applyAliasEnvFallbacks();
}

export function getLonaConfig() {
  initializeLonaCredentials();

  return {
    gatewayUrl: LONA_GATEWAY_URL,
    agentId: process.env.LONA_AGENT_ID ?? 'trade-nexus',
    agentName: process.env.LONA_AGENT_NAME ?? 'Trade Nexus Orchestrator',
    registrationSecret: process.env.LONA_AGENT_REGISTRATION_SECRET ?? '',
    token: process.env.LONA_AGENT_TOKEN ?? '',
  };
}

export function getLiveEngineConfig() {
  return {
    url: LIVE_ENGINE_URL,
    serviceKey: LIVE_ENGINE_SERVICE_KEY,
  };
}

export function getAIConfig() {
  return {
    xaiApiKey: process.env.XAI_API_KEY ?? '',
    model: 'grok-4-1-fast-non-reasoning',
  };
}

export function validateConfig(required: string[]) {
  initializeLonaCredentials();

  const missing = required.filter((key) => !process.env[key]);
  if (missing.length > 0) {
    throw new Error(`Missing required env vars: ${missing.join(', ')}`);
  }
}
