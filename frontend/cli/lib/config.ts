export const LONA_GATEWAY_URL = process.env.LONA_GATEWAY_URL ?? 'https://gateway.lona.agency';
export const LIVE_ENGINE_URL = process.env.LIVE_ENGINE_URL ?? 'https://live.lona.agency';
export const LIVE_ENGINE_SERVICE_KEY = process.env.LIVE_ENGINE_SERVICE_KEY ?? '';

export function getLonaConfig() {
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
  const missing = required.filter((key) => !process.env[key]);
  if (missing.length > 0) {
    throw new Error(`Missing required env vars: ${missing.join(', ')}`);
  }
}
