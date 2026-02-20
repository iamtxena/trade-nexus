import { describe, expect, test } from 'bun:test';

import type { ValidationRunArtifact, ValidationRunSummary } from '@/lib/validation/types';

import { resolveValidationRunTimeline } from '../review-run-timeline';

const RUN: ValidationRunSummary = {
  id: 'valrun-001',
  status: 'completed',
  profile: 'STANDARD',
  schemaVersion: 'validation-run.v1',
  finalDecision: 'conditional_pass',
  createdAt: '2026-02-18T10:00:00Z',
  updatedAt: '2026-02-18T10:20:00Z',
};

const ARTIFACT: ValidationRunArtifact = {
  schemaVersion: 'validation-run.v1',
  runId: RUN.id,
  createdAt: '2026-02-18T10:10:00Z',
  requestId: 'req-validation-001',
  tenantId: 'tenant-001',
  userId: 'user-001',
  strategyRef: {
    strategyId: 'strat-001',
    provider: 'lona',
    providerRefId: 'lona-001',
  },
  inputs: {
    prompt: 'prompt',
    requestedIndicators: ['ema'],
    datasetIds: ['dataset-1'],
    backtestReportRef: 'blob://backtest-report',
  },
  outputs: {
    strategyCodeRef: 'blob://strategy.py',
    backtestReportRef: 'blob://backtest-report',
    tradesRef: 'blob://trades',
    executionLogsRef: 'blob://logs',
    chartPayloadRef: 'blob://charts',
  },
  deterministicChecks: {
    indicatorFidelity: {
      status: 'pass',
      missingIndicators: [],
    },
    tradeCoherence: {
      status: 'fail',
      violations: ['exit before entry'],
    },
    metricConsistency: {
      status: 'pass',
      driftPct: 0.87,
    },
  },
  agentReview: {
    status: 'conditional_pass',
    summary: 'Needs tighter risk limits before release.',
    findings: [],
  },
  traderReview: {
    required: true,
    status: 'requested',
    comments: ['Please tighten drawdown guardrail.'],
  },
  policy: {
    profile: 'STANDARD',
    blockMergeOnFail: true,
    blockReleaseOnFail: true,
    blockMergeOnAgentFail: true,
    blockReleaseOnAgentFail: false,
    requireTraderReview: true,
    hardFailOnMissingIndicators: true,
    failClosedOnEvidenceUnavailable: true,
  },
  finalDecision: 'conditional_pass',
};

describe('resolveValidationRunTimeline', () => {
  test('creates chronological run events with deterministic checks and decisions', () => {
    const timeline = resolveValidationRunTimeline(RUN, ARTIFACT);
    expect(timeline.map((event) => event.title)).toEqual([
      'Run Created',
      'Indicator Fidelity Check',
      'Trade Coherence Check',
      'Metric Consistency Check',
      'Agent Review',
      'Trader Review',
      'Final Decision',
    ]);
    expect(timeline[2]).toMatchObject({
      title: 'Trade Coherence Check',
      tone: 'danger',
    });
    expect(timeline.at(-1)).toMatchObject({
      title: 'Final Decision',
      tone: 'pending',
    });
  });
});
