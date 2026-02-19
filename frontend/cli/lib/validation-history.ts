import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

export type ValidationRunHistoryEntry = {
  runId: string;
  requestId?: string;
  strategyId?: string;
  profile?: string;
  status?: string;
  finalDecision?: string;
  updatedAt: string;
};

export type ValidationReplayHistoryEntry = {
  replayId: string;
  requestId?: string;
  baselineId: string;
  candidateRunId: string;
  status?: string;
  decision?: string;
  updatedAt: string;
};

type ValidationHistory = {
  runs: ValidationRunHistoryEntry[];
  replays: ValidationReplayHistoryEntry[];
  updatedAt: string;
};

function createEmptyHistory(): ValidationHistory {
  return {
    runs: [],
    replays: [],
    updatedAt: new Date(0).toISOString(),
  };
}

export function getValidationHistoryPath(): string {
  const cliHome = process.env.NEXUS_CLI_HOME?.trim() || join(homedir(), '.trade-nexus');
  return join(cliHome, 'validation-history.json');
}

export function readValidationHistory(filePath = getValidationHistoryPath()): ValidationHistory {
  if (!existsSync(filePath)) return createEmptyHistory();

  try {
    const raw = JSON.parse(readFileSync(filePath, 'utf-8')) as Partial<ValidationHistory>;
    return {
      runs: Array.isArray(raw.runs) ? raw.runs : [],
      replays: Array.isArray(raw.replays) ? raw.replays : [],
      updatedAt: typeof raw.updatedAt === 'string' ? raw.updatedAt : new Date(0).toISOString(),
    };
  } catch {
    return createEmptyHistory();
  }
}

function writeValidationHistory(
  history: ValidationHistory,
  filePath = getValidationHistoryPath(),
): void {
  mkdirSync(join(filePath, '..'), { recursive: true });
  writeFileSync(filePath, `${JSON.stringify(history, null, 2)}\n`, 'utf-8');
}

export function recordValidationRun(
  entry: Omit<ValidationRunHistoryEntry, 'updatedAt'> & { updatedAt?: string },
  filePath = getValidationHistoryPath(),
): void {
  const history = readValidationHistory(filePath);
  const updatedAt = entry.updatedAt ?? new Date().toISOString();

  const existingIdx = history.runs.findIndex((item) => item.runId === entry.runId);
  const next: ValidationRunHistoryEntry = {
    ...(existingIdx >= 0 ? history.runs[existingIdx] : {}),
    ...entry,
    updatedAt,
  };
  if (existingIdx >= 0) {
    history.runs[existingIdx] = next;
  } else {
    history.runs.push(next);
  }

  history.updatedAt = updatedAt;
  writeValidationHistory(history, filePath);
}

export function recordValidationReplay(
  entry: Omit<ValidationReplayHistoryEntry, 'updatedAt'> & { updatedAt?: string },
  filePath = getValidationHistoryPath(),
): void {
  const history = readValidationHistory(filePath);
  const updatedAt = entry.updatedAt ?? new Date().toISOString();

  const existingIdx = history.replays.findIndex((item) => item.replayId === entry.replayId);
  const next: ValidationReplayHistoryEntry = {
    ...(existingIdx >= 0 ? history.replays[existingIdx] : {}),
    ...entry,
    updatedAt,
  };
  if (existingIdx >= 0) {
    history.replays[existingIdx] = next;
  } else {
    history.replays.push(next);
  }

  history.updatedAt = updatedAt;
  writeValidationHistory(history, filePath);
}
