export type ValidationProfile = 'FAST' | 'STANDARD' | 'EXPERT';
export type ValidationRunStatus = 'queued' | 'running' | 'completed' | 'failed';
export type ValidationDecision = 'pass' | 'conditional_pass' | 'fail';
export type ValidationCheckStatus = 'pass' | 'fail';
export type ValidationReviewerType = 'agent' | 'trader';
export type ValidationTraderReviewStatus = 'not_requested' | 'requested' | 'approved' | 'rejected';
export type ValidationRenderFormat = 'html' | 'pdf';
export type ValidationRenderStatus = 'queued' | 'running' | 'completed' | 'failed';
export type ValidationArtifactType = 'validation_run' | 'validation_llm_snapshot';

export interface ValidationRunSummary {
  id: string;
  status: ValidationRunStatus;
  profile: ValidationProfile;
  schemaVersion: 'validation-run.v1';
  finalDecision: ValidationDecision;
  createdAt: string;
  updatedAt: string;
}

export interface ValidationRunResponse {
  requestId: string;
  run: ValidationRunSummary;
}

export interface ValidationRunListResponse {
  requestId: string;
  runs: ValidationRunSummary[];
}

export interface ValidationStrategyRef {
  strategyId: string;
  provider: string;
  providerRefId: string;
}

export interface ValidationRunInputs {
  prompt: string;
  requestedIndicators: string[];
  datasetIds: string[];
  backtestReportRef: string;
}

export interface ValidationRunOutputs {
  strategyCodeRef: string;
  backtestReportRef: string;
  tradesRef: string;
  executionLogsRef: string;
  chartPayloadRef: string;
}

export interface ValidationIndicatorFidelityCheck {
  status: ValidationCheckStatus;
  missingIndicators: string[];
}

export interface ValidationTradeCoherenceCheck {
  status: ValidationCheckStatus;
  violations: string[];
}

export interface ValidationMetricConsistencyCheck {
  status: ValidationCheckStatus;
  driftPct: number;
}

export interface ValidationDeterministicChecks {
  indicatorFidelity: ValidationIndicatorFidelityCheck;
  tradeCoherence: ValidationTradeCoherenceCheck;
  metricConsistency: ValidationMetricConsistencyCheck;
}

export interface ValidationReviewFinding {
  id: string;
  priority: number;
  confidence: number;
  summary: string;
  evidenceRefs: string[];
}

export interface ValidationAgentReviewBudgetLimits {
  maxRuntimeSeconds: number;
  maxTokens: number;
  maxToolCalls: number;
  maxFindings: number;
}

export interface ValidationAgentReviewBudgetUsage {
  runtimeSeconds: number;
  tokensUsed: number;
  toolCallsUsed: number;
}

export interface ValidationAgentReviewBudget {
  profile: ValidationProfile;
  limits: ValidationAgentReviewBudgetLimits;
  usage: ValidationAgentReviewBudgetUsage;
  withinBudget: boolean;
  breachReason: string | null;
}

export interface ValidationAgentReview {
  status: ValidationDecision;
  summary: string;
  findings: ValidationReviewFinding[];
  budget: ValidationAgentReviewBudget;
}

export interface ValidationTraderReview {
  required: boolean;
  status: ValidationTraderReviewStatus;
  comments: string[];
}

export interface ValidationPolicyProfile {
  profile: ValidationProfile;
  blockMergeOnFail: boolean;
  blockReleaseOnFail: boolean;
  blockMergeOnAgentFail: boolean;
  blockReleaseOnAgentFail: boolean;
  requireTraderReview: boolean;
  hardFailOnMissingIndicators: boolean;
  failClosedOnEvidenceUnavailable: boolean;
}

export interface ValidationRunArtifact {
  schemaVersion: 'validation-run.v1';
  runId: string;
  createdAt: string;
  requestId: string;
  tenantId: string;
  userId: string;
  strategyRef: ValidationStrategyRef;
  inputs: ValidationRunInputs;
  outputs: ValidationRunOutputs;
  deterministicChecks: ValidationDeterministicChecks;
  agentReview: ValidationAgentReview;
  traderReview: ValidationTraderReview;
  policy: ValidationPolicyProfile;
  finalDecision: ValidationDecision;
}

export interface ValidationLlmSnapshotArtifact {
  schemaVersion: 'validation-llm-snapshot.v1';
  runId: string;
  profile: ValidationProfile;
  prompt: string;
  requestedIndicators: string[];
  deterministicChecks: ValidationDeterministicChecks;
  findings: Array<Pick<ValidationReviewFinding, 'priority' | 'confidence' | 'summary'>>;
  evidenceRefs: string[];
  finalDecision: ValidationDecision;
}

export type ValidationArtifact = ValidationRunArtifact | ValidationLlmSnapshotArtifact;

export interface ValidationArtifactResponse {
  requestId: string;
  artifactType: ValidationArtifactType;
  artifact: ValidationArtifact;
}

export interface ValidationRunReviewRequestPayload {
  reviewerType: ValidationReviewerType;
  decision: ValidationDecision;
  summary?: string;
  findings?: ValidationReviewFinding[];
  comments?: string[];
}

export interface ValidationRunReviewResponse {
  requestId: string;
  runId: string;
  reviewAccepted: boolean;
}

export interface ValidationRenderRequestPayload {
  format: ValidationRenderFormat;
}

export interface ValidationRenderJob {
  runId: string;
  format: ValidationRenderFormat;
  status: ValidationRenderStatus;
  artifactRef?: string | null;
}

export interface ValidationRenderResponse {
  requestId: string;
  render: ValidationRenderJob;
}

export interface CreateValidationRunRequestPayload {
  strategyId: string;
  providerRefId?: string;
  prompt?: string;
  requestedIndicators: string[];
  datasetIds: string[];
  backtestReportRef: string;
  policy: ValidationPolicyProfile;
}

export interface ErrorPayload {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
  requestId?: string;
}

export function isValidationRunArtifact(
  artifact: ValidationArtifact,
): artifact is ValidationRunArtifact {
  return (
    'traderReview' in artifact &&
    'agentReview' in artifact &&
    'deterministicChecks' in artifact &&
    'policy' in artifact
  );
}
