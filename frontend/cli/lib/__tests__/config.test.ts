import { afterEach, describe, expect, test } from 'bun:test';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { getLonaConfig, initializeLonaCredentials, validateConfig } from '../config';

const originalEnv = { ...process.env };
const tempDirs: string[] = [];

function makeCredentialsFile(payload: Record<string, string>): string {
  const dir = mkdtempSync(join(tmpdir(), 'lona-creds-'));
  tempDirs.push(dir);
  const filePath = join(dir, 'credentials.json');
  writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf-8');
  return filePath;
}

afterEach(() => {
  process.env = { ...originalEnv };

  while (tempDirs.length > 0) {
    const dir = tempDirs.pop();
    if (dir) rmSync(dir, { recursive: true, force: true });
  }
});

describe('cli config credential normalization', () => {
  test('loads token and agent id from lona credentials file', () => {
    delete process.env.LONA_AGENT_TOKEN;
    delete process.env.LONA_AGENT_ID;
    delete process.env.LONA_API_KEY;
    delete process.env.LONA_USER_ID;

    process.env.LONA_CREDENTIALS_FILE = makeCredentialsFile({
      lona_token: 'file-token',
      agent_id: 'file-agent',
    });

    initializeLonaCredentials({ force: true });
    const config = getLonaConfig();

    expect(config.token).toBe('file-token');
    expect(config.agentId).toBe('file-agent');
    expect(process.env.LONA_AGENT_TOKEN ?? '').toBe('file-token');
    expect(process.env.LONA_AGENT_ID ?? '').toBe('file-agent');
  });

  test('maps MCP env aliases to canonical LONA_AGENT_* vars', () => {
    delete process.env.LONA_AGENT_TOKEN;
    delete process.env.LONA_AGENT_ID;
    process.env.LONA_API_KEY = 'alias-token';
    process.env.LONA_USER_ID = 'alias-user';

    initializeLonaCredentials({ force: true });
    const config = getLonaConfig();

    expect(config.token).toBe('alias-token');
    expect(config.agentId).toBe('alias-user');
    expect(process.env.LONA_AGENT_TOKEN ?? '').toBe('alias-token');
    expect(process.env.LONA_AGENT_ID ?? '').toBe('alias-user');
  });

  test('keeps explicit canonical env values over file fallbacks', () => {
    process.env.LONA_AGENT_TOKEN = 'env-token';
    process.env.LONA_AGENT_ID = 'env-agent';
    process.env.LONA_CREDENTIALS_FILE = makeCredentialsFile({
      lona_token: 'file-token',
      agent_id: 'file-agent',
    });

    initializeLonaCredentials({ force: true });
    const config = getLonaConfig();

    expect(config.token).toBe('env-token');
    expect(config.agentId).toBe('env-agent');
  });

  test('validateConfig accepts alias env after normalization', () => {
    delete process.env.LONA_AGENT_TOKEN;
    delete process.env.LONA_AGENT_ID;
    process.env.LONA_API_KEY = 'alias-token';
    process.env.LONA_USER_ID = 'alias-user';

    initializeLonaCredentials({ force: true });

    expect(() => validateConfig(['LONA_AGENT_TOKEN'])).not.toThrow();
  });
});
