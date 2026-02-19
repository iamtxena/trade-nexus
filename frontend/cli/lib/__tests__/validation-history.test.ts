import { afterEach, describe, expect, test } from 'bun:test';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { readValidationHistory, recordValidationRun } from '../validation-history';

const tempDirs: string[] = [];

function makeTempPath(name: string): string {
  const dir = mkdtempSync(join(tmpdir(), 'validation-history-'));
  tempDirs.push(dir);
  return join(dir, name);
}

afterEach(() => {
  while (tempDirs.length > 0) {
    const dir = tempDirs.pop();
    if (dir) rmSync(dir, { recursive: true, force: true });
  }
});

describe('validation history store', () => {
  test('does not leak default in-memory state across missing files', () => {
    const fileA = makeTempPath('history-a.json');
    const fileB = makeTempPath('history-b.json');

    recordValidationRun({ runId: 'valrun-a', status: 'queued' }, fileA);

    const fresh = readValidationHistory(fileB);
    expect(fresh.runs.length).toBe(0);
    expect(fresh.replays.length).toBe(0);
  });

  test('updating timestamp-only entry does not overwrite existing run status', () => {
    const file = makeTempPath('history.json');

    recordValidationRun({ runId: 'valrun-001', status: 'completed' }, file);
    recordValidationRun({ runId: 'valrun-001' }, file);

    const current = readValidationHistory(file);
    expect(current.runs.length).toBe(1);
    expect(current.runs[0]?.status).toBe('completed');
  });
});
