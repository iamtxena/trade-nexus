import type {
  ValidationCheckStatus,
  ValidationRunArtifact,
  ValidationRunSummary,
} from '@/lib/validation/types';

export type ValidationTimelineTone = 'neutral' | 'pending' | 'success' | 'danger';

export interface ValidationTimelineEvent {
  id: string;
  title: string;
  detail: string;
  timestamp: string;
  tone: ValidationTimelineTone;
}

function toTimestamp(value: string): number {
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

function checkTone(status: ValidationCheckStatus): ValidationTimelineTone {
  return status === 'pass' ? 'success' : 'danger';
}

function decisionTone(
  decision: ValidationRunSummary['finalDecision'] | ValidationRunArtifact['agentReview']['status'],
): ValidationTimelineTone {
  switch (decision) {
    case 'pass':
      return 'success';
    case 'fail':
      return 'danger';
    default:
      return 'pending';
  }
}

export function resolveValidationRunTimeline(
  run: ValidationRunSummary,
  artifact: ValidationRunArtifact,
): ValidationTimelineEvent[] {
  const events: ValidationTimelineEvent[] = [
    {
      id: `${run.id}-created`,
      title: 'Run Created',
      detail: `Profile ${run.profile}. Initial status: ${run.status}.`,
      timestamp: run.createdAt,
      tone: run.status === 'failed' ? 'danger' : 'pending',
    },
    {
      id: `${run.id}-indicator-fidelity`,
      title: 'Indicator Fidelity Check',
      detail:
        artifact.deterministicChecks.indicatorFidelity.status === 'pass'
          ? 'Requested indicators were resolved in candidate strategy.'
          : `Missing indicators: ${
              artifact.deterministicChecks.indicatorFidelity.missingIndicators.join(', ') || 'n/a'
            }.`,
      timestamp: artifact.createdAt,
      tone: checkTone(artifact.deterministicChecks.indicatorFidelity.status),
    },
    {
      id: `${run.id}-trade-coherence`,
      title: 'Trade Coherence Check',
      detail:
        artifact.deterministicChecks.tradeCoherence.status === 'pass'
          ? 'Trade sequence passed coherence checks.'
          : `Violations: ${artifact.deterministicChecks.tradeCoherence.violations.join(', ') || 'n/a'}.`,
      timestamp: artifact.createdAt,
      tone: checkTone(artifact.deterministicChecks.tradeCoherence.status),
    },
    {
      id: `${run.id}-metric-consistency`,
      title: 'Metric Consistency Check',
      detail: `Drift: ${artifact.deterministicChecks.metricConsistency.driftPct.toFixed(2)}%.`,
      timestamp: artifact.createdAt,
      tone: checkTone(artifact.deterministicChecks.metricConsistency.status),
    },
    {
      id: `${run.id}-agent-review`,
      title: 'Agent Review',
      detail: artifact.agentReview.summary,
      timestamp: run.updatedAt,
      tone: decisionTone(artifact.agentReview.status),
    },
    {
      id: `${run.id}-trader-review`,
      title: 'Trader Review',
      detail: `Status: ${artifact.traderReview.status}. Comments: ${artifact.traderReview.comments.length}.`,
      timestamp: run.updatedAt,
      tone:
        artifact.traderReview.status === 'approved'
          ? 'success'
          : artifact.traderReview.status === 'rejected'
            ? 'danger'
            : artifact.traderReview.status === 'requested'
              ? 'pending'
              : 'neutral',
    },
    {
      id: `${run.id}-final-decision`,
      title: 'Final Decision',
      detail: `Decision: ${run.finalDecision}.`,
      timestamp: run.updatedAt,
      tone: decisionTone(run.finalDecision),
    },
  ];

  return [...events].sort(
    (left, right) => toTimestamp(left.timestamp) - toTimestamp(right.timestamp),
  );
}
