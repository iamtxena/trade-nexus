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

export type ValidationSharePermission = 'view' | 'review';
export type ValidationInviteStatus = 'pending' | 'accepted' | 'revoked' | 'expired';
export type ValidationShareStatus = 'active' | 'revoked';
export type ValidationBotStatus = 'active' | 'suspended' | 'revoked';
export type ValidationBotRegistrationPath = 'invite_code_trial' | 'partner_bootstrap';
export type ValidationBotKeyStatus = 'active' | 'rotated' | 'revoked';

export interface ValidationBot {
  id: string;
  tenantId: string;
  ownerUserId: string;
  name: string;
  status: ValidationBotStatus;
  registrationPath: ValidationBotRegistrationPath;
  trialExpiresAt?: string | null;
  metadata?: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface ValidationBotKeyMetadata {
  id: string;
  botId: string;
  keyPrefix: string;
  status: ValidationBotKeyStatus;
  createdAt: string;
  lastUsedAt?: string | null;
  revokedAt?: string | null;
}

export interface ValidationBotUsageMetadata {
  totalRequests?: number;
  successfulRequests?: number;
  failedRequests?: number;
  lastSeenAt?: string | null;
}

export interface ValidationBotSummary extends ValidationBot {
  keys: ValidationBotKeyMetadata[];
  usage?: ValidationBotUsageMetadata;
}

export interface ValidationBotListResponse {
  requestId: string;
  bots: ValidationBotSummary[];
}

export interface ValidationBotIssuedApiKey {
  rawKey: string;
  key: ValidationBotKeyMetadata;
}

export interface ValidationBotRegistration {
  id: string;
  botId: string;
  registrationPath: ValidationBotRegistrationPath;
  status: 'completed';
  audit?: Record<string, unknown>;
  createdAt: string;
}

export interface ValidationBotRegistrationResponse {
  requestId: string;
  bot: ValidationBot;
  registration: ValidationBotRegistration;
  issuedKey: ValidationBotIssuedApiKey;
}

export interface ValidationBotKeyRotationResponse {
  requestId: string;
  botId: string;
  issuedKey: ValidationBotIssuedApiKey;
}

export interface ValidationBotKeyMetadataResponse {
  requestId: string;
  botId: string;
  key: ValidationBotKeyMetadata;
}

export interface CreateValidationBotInviteCodeRegistrationPayload {
  inviteCode: string;
  botName: string;
  metadata?: Record<string, unknown>;
}

export interface CreateValidationBotPartnerBootstrapPayload {
  partnerKey: string;
  partnerSecret: string;
  ownerEmail: string;
  botName: string;
  metadata?: Record<string, unknown>;
}

export interface CreateValidationBotKeyRotationPayload {
  reason?: string;
}

export interface CreateValidationBotKeyRevocationPayload {
  reason?: string;
}

export interface ValidationShareInvite {
  id: string;
  runId: string;
  email: string;
  permission: ValidationSharePermission;
  status: ValidationInviteStatus;
  invitedByUserId: string;
  invitedByActorType?: 'user' | 'bot';
  createdAt: string;
  expiresAt?: string | null;
  acceptedAt?: string | null;
  revokedAt?: string | null;
}

export interface ValidationShareInviteResponse {
  requestId: string;
  invite: ValidationShareInvite;
}

export interface ValidationShareInviteListResponse {
  requestId: string;
  items: ValidationShareInvite[];
  nextCursor?: string | null;
}

export interface CreateValidationShareInvitePayload {
  email: string;
  permission: ValidationSharePermission;
  message?: string;
  expiresAt?: string;
}

export interface ValidationSharedRunSummary {
  runId: string;
  permission: ValidationSharePermission;
  status: ValidationRunStatus;
  profile: ValidationProfile;
  finalDecision: ValidationDecision;
  ownerUserId?: string;
  sharedAt?: string;
  createdAt: string;
  updatedAt: string;
}

export interface ValidationSharedRunListResponse {
  requestId: string;
  items: ValidationSharedRunSummary[];
  nextCursor?: string | null;
}

export interface ValidationReviewComment {
  id: string;
  runId: string;
  tenantId?: string;
  userId?: string;
  body: string;
  evidenceRefs: string[];
  createdAt: string;
}

export interface ValidationReviewDecision {
  runId: string;
  action: 'approve' | 'reject';
  decision: ValidationDecision;
  reason: string;
  evidenceRefs: string[];
  decidedByTenantId?: string;
  decidedByUserId?: string;
  createdAt: string;
}

export interface ValidationSharedRunDetailResponse {
  requestId: string;
  run: ValidationRunSummary;
  artifact: ValidationRunArtifact;
  permission: ValidationSharePermission;
  comments?: ValidationReviewComment[];
  decision?: ValidationReviewDecision | null;
}

export interface CreateSharedValidationCommentPayload {
  body: string;
  evidenceRefs?: string[];
}

export interface CreateSharedValidationDecisionPayload {
  decision: ValidationDecision;
  reason: string;
  action: 'approve' | 'reject';
  evidenceRefs?: string[];
}
