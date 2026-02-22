"""Pydantic schemas for Platform API v2 KB/Data extensions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from src.platform_api.schemas_v1 import MarketScanIdea


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    assets: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=100)


class KnowledgeSearchItem(BaseModel):
    kind: str
    id: str
    title: str
    summary: str
    score: float
    evidence: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    requestId: str
    items: list[KnowledgeSearchItem]


class KnowledgePattern(BaseModel):
    id: str
    name: str
    type: str
    description: str
    suitableRegimes: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    timeframes: list[str] = Field(default_factory=list)
    confidenceScore: float
    sourceRef: str | None = None
    schemaVersion: str
    createdAt: str
    updatedAt: str


class KnowledgePatternListResponse(BaseModel):
    requestId: str
    items: list[KnowledgePattern]


class KnowledgeRegime(BaseModel):
    id: str
    asset: str
    regime: str
    volatility: str
    indicators: dict[str, float] = Field(default_factory=dict)
    startAt: str
    endAt: str | None = None
    notes: str | None = None
    schemaVersion: str
    createdAt: str


class KnowledgeRegimeResponse(BaseModel):
    requestId: str
    regime: KnowledgeRegime


class BacktestDataExportRequest(BaseModel):
    datasetIds: list[str] = Field(min_length=1)
    assetClasses: list[str] = Field(default_factory=list)


class BacktestDataExport(BaseModel):
    id: str
    status: str
    datasetIds: list[str]
    assetClasses: list[str]
    downloadUrl: str | None = None
    lineage: dict[str, Any] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class BacktestDataExportResponse(BaseModel):
    requestId: str
    export: BacktestDataExport


class MarketScanV2Response(BaseModel):
    requestId: str
    regimeSummary: str
    strategyIdeas: list[MarketScanIdea]
    knowledgeEvidence: list[KnowledgeSearchItem]
    dataContextSummary: str


ConversationChannel = Literal["cli", "web", "openclaw"]
ConversationRole = Literal["user", "assistant", "system"]
ConversationSessionStatus = Literal["active", "closed"]


class CreateConversationSessionRequest(BaseModel):
    channel: ConversationChannel
    topic: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _reject_null_topic(cls, value: Any) -> Any:
        if isinstance(value, dict) and "topic" in value and value["topic"] is None:
            raise ValueError("topic must be omitted or a non-empty string.")
        return value


class ConversationSession(BaseModel):
    id: str
    channel: ConversationChannel
    status: ConversationSessionStatus
    topic: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str
    lastTurnAt: str | None = None


class ConversationSessionResponse(BaseModel):
    requestId: str
    session: ConversationSession


class CreateConversationTurnRequest(BaseModel):
    role: ConversationRole
    message: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationTurn(BaseModel):
    id: str
    sessionId: str
    role: ConversationRole
    message: str
    suggestions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str


class ConversationTurnResponse(BaseModel):
    requestId: str
    sessionId: str
    turn: ConversationTurn


ValidationProfile = Literal["FAST", "STANDARD", "EXPERT"]
ValidationDecision = Literal["pass", "conditional_pass", "fail"]
ValidationRunDecision = Literal["pending", "pass", "conditional_pass", "fail"]
ValidationRunStatus = Literal["queued", "running", "completed", "failed"]
ValidationCheckStatus = Literal["pass", "fail"]
ValidationTraderReviewStatus = Literal["not_requested", "requested", "approved", "rejected"]
ValidationArtifactType = Literal["validation_run", "validation_llm_snapshot"]
ValidationRenderFormat = Literal["html", "pdf"]
ValidationReplayGateStatus = Literal["pass", "blocked"]
ValidationActorType = Literal["user", "bot"]


class ValidationPolicyProfile(BaseModel):
    profile: str = Field(min_length=1)
    blockMergeOnFail: bool
    blockReleaseOnFail: bool
    blockMergeOnAgentFail: bool
    blockReleaseOnAgentFail: bool
    requireTraderReview: bool
    hardFailOnMissingIndicators: bool
    failClosedOnEvidenceUnavailable: bool


class ValidationRunActorMetadata(BaseModel):
    actorType: ValidationActorType
    actorId: str = Field(min_length=1)
    userId: str | None = None
    botId: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationRun(BaseModel):
    id: str
    status: ValidationRunStatus
    profile: ValidationProfile
    schemaVersion: Literal["validation-run.v1"]
    finalDecision: ValidationRunDecision
    actor: ValidationRunActorMetadata | None = None
    createdAt: str
    updatedAt: str


class ValidationRunResponse(BaseModel):
    requestId: str
    run: ValidationRun


class ValidationRunListResponse(BaseModel):
    requestId: str
    runs: list[ValidationRun] = Field(default_factory=list)


class ValidationStrategyRef(BaseModel):
    strategyId: str
    provider: Literal["lona"]
    providerRefId: str


class ValidationRunInputs(BaseModel):
    prompt: str
    requestedIndicators: list[str] = Field(min_length=1)
    datasetIds: list[str] = Field(min_length=1)
    backtestReportRef: str


class ValidationRunOutputs(BaseModel):
    strategyCodeRef: str
    backtestReportRef: str
    tradesRef: str
    executionLogsRef: str
    chartPayloadRef: str


class ValidationIndicatorFidelityCheck(BaseModel):
    status: ValidationCheckStatus
    missingIndicators: list[str] = Field(default_factory=list)


class ValidationTradeCoherenceCheck(BaseModel):
    status: ValidationCheckStatus
    violations: list[str] = Field(default_factory=list)


class ValidationMetricConsistencyCheck(BaseModel):
    status: ValidationCheckStatus
    driftPct: float = Field(ge=0)


class ValidationDeterministicChecks(BaseModel):
    indicatorFidelity: ValidationIndicatorFidelityCheck
    tradeCoherence: ValidationTradeCoherenceCheck
    metricConsistency: ValidationMetricConsistencyCheck


class ValidationReviewFinding(BaseModel):
    id: str = Field(min_length=1)
    priority: int = Field(ge=0, le=3)
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=1)
    evidenceRefs: list[str] = Field(min_length=1)


class ValidationAgentReviewBudgetLimits(BaseModel):
    maxRuntimeSeconds: float = Field(gt=0)
    maxTokens: int = Field(ge=1)
    maxToolCalls: int = Field(ge=0)
    maxFindings: int = Field(ge=1)


class ValidationAgentReviewBudgetUsage(BaseModel):
    runtimeSeconds: float = Field(ge=0)
    tokensUsed: int = Field(ge=0)
    toolCallsUsed: int = Field(ge=0)


class ValidationAgentReviewBudget(BaseModel):
    profile: ValidationProfile
    limits: ValidationAgentReviewBudgetLimits
    usage: ValidationAgentReviewBudgetUsage
    withinBudget: bool
    breachReason: str | None = None


class ValidationAgentReview(BaseModel):
    status: ValidationDecision
    summary: str
    findings: list[ValidationReviewFinding] = Field(default_factory=list)
    budget: ValidationAgentReviewBudget


class ValidationTraderReview(BaseModel):
    required: bool
    status: ValidationTraderReviewStatus
    comments: list[str] = Field(default_factory=list)


class ValidationRunArtifact(BaseModel):
    schemaVersion: Literal["validation-run.v1"]
    runId: str
    createdAt: str
    requestId: str
    tenantId: str
    userId: str
    actor: ValidationRunActorMetadata | None = None
    strategyRef: ValidationStrategyRef
    inputs: ValidationRunInputs
    outputs: ValidationRunOutputs
    deterministicChecks: ValidationDeterministicChecks
    agentReview: ValidationAgentReview
    traderReview: ValidationTraderReview
    policy: ValidationPolicyProfile
    finalDecision: ValidationDecision


class ValidationSnapshotDeterministicChecks(BaseModel):
    indicatorFidelityStatus: ValidationCheckStatus
    tradeCoherenceStatus: ValidationCheckStatus
    metricConsistencyStatus: ValidationCheckStatus


class ValidationSnapshotEvidenceRef(BaseModel):
    kind: Literal["strategy_code", "backtest_report", "trades", "execution_logs", "chart_payload"]
    ref: str


class ValidationLlmSnapshotArtifactFinding(BaseModel):
    priority: int = Field(ge=0, le=3)
    confidence: float = Field(ge=0, le=1)
    summary: str = Field(min_length=1)


class ValidationLlmSnapshotArtifact(BaseModel):
    schemaVersion: Literal["validation-llm-snapshot.v1"]
    runId: str
    sourceSchemaVersion: Literal["validation-run.v1"]
    generatedAt: str
    strategyId: str
    requestedIndicators: list[str] = Field(min_length=1)
    deterministicChecks: ValidationSnapshotDeterministicChecks
    policy: ValidationPolicyProfile
    evidenceRefs: list[ValidationSnapshotEvidenceRef] = Field(min_length=1)
    findings: list[ValidationLlmSnapshotArtifactFinding] = Field(default_factory=list)
    finalDecision: ValidationDecision


class ValidationArtifactResponse(BaseModel):
    requestId: str
    artifactType: ValidationArtifactType
    artifact: ValidationRunArtifact | ValidationLlmSnapshotArtifact


class CreateValidationRunRequest(BaseModel):
    strategyId: str
    providerRefId: str | None = None
    prompt: str | None = None
    requestedIndicators: list[str] = Field(min_length=1)
    datasetIds: list[str] = Field(min_length=1)
    backtestReportRef: str
    policy: ValidationPolicyProfile


class CreateValidationRunReviewRequest(BaseModel):
    reviewerType: str = Field(min_length=1)
    decision: str = Field(min_length=1)
    summary: str | None = None
    findings: list[ValidationReviewFinding] = Field(default_factory=list)
    comments: list[str] = Field(default_factory=list)


class ValidationRunReviewResponse(BaseModel):
    requestId: str
    runId: str
    reviewAccepted: bool


class CreateValidationRenderRequest(BaseModel):
    format: str = Field(min_length=1)


class ValidationRenderJob(BaseModel):
    runId: str
    format: ValidationRenderFormat
    status: Literal["queued", "running", "completed", "failed"]
    artifactRef: str | None = None


class ValidationRenderResponse(BaseModel):
    requestId: str
    render: ValidationRenderJob


ValidationReviewDecisionAction = Literal["approve", "reject"]


class ValidationReviewRunSummary(BaseModel):
    id: str
    status: ValidationRunStatus
    profile: ValidationProfile
    finalDecision: ValidationRunDecision
    traderReviewStatus: ValidationTraderReviewStatus
    commentCount: int = Field(ge=0)
    pendingDecision: bool
    createdAt: str
    updatedAt: str


class ValidationReviewRunListResponse(BaseModel):
    requestId: str
    items: list[ValidationReviewRunSummary] = Field(default_factory=list)
    nextCursor: str | None = None


class ValidationReviewComment(BaseModel):
    id: str
    runId: str
    tenantId: str
    userId: str
    body: str = Field(min_length=1)
    evidenceRefs: list[str] = Field(default_factory=list)
    createdAt: str


class CreateValidationReviewCommentRequest(BaseModel):
    body: str = Field(min_length=1)
    evidenceRefs: list[str] = Field(default_factory=list)


class ValidationReviewCommentResponse(BaseModel):
    requestId: str
    runId: str
    commentAccepted: bool
    comment: ValidationReviewComment


class ValidationReviewDecision(BaseModel):
    runId: str
    action: ValidationReviewDecisionAction
    decision: ValidationDecision
    reason: str = Field(min_length=1)
    evidenceRefs: list[str] = Field(default_factory=list)
    decidedByTenantId: str
    decidedByUserId: str
    createdAt: str


class CreateValidationReviewDecisionRequest(BaseModel):
    action: ValidationReviewDecisionAction
    decision: ValidationDecision
    reason: str = Field(min_length=1)
    evidenceRefs: list[str] = Field(default_factory=list)


class ValidationReviewDecisionResponse(BaseModel):
    requestId: str
    runId: str
    decisionAccepted: bool
    decision: ValidationReviewDecision


class CreateValidationReviewRenderRequest(BaseModel):
    format: ValidationRenderFormat


class ValidationReviewRenderJob(BaseModel):
    runId: str
    format: ValidationRenderFormat
    status: Literal["queued", "running", "completed", "failed"]
    artifactRef: str | None = None
    downloadUrl: str | None = None
    checksumSha256: str | None = None
    expiresAt: str | None = None
    requestedAt: str
    updatedAt: str


class ValidationReviewRenderResponse(BaseModel):
    requestId: str
    render: ValidationReviewRenderJob


class ValidationReviewArtifact(BaseModel):
    schemaVersion: Literal["validation-review.v1"]
    run: ValidationRun
    artifact: ValidationRunArtifact
    comments: list[ValidationReviewComment] = Field(default_factory=list)
    decision: ValidationReviewDecision | None = None
    renders: list[ValidationReviewRenderJob] = Field(default_factory=list)


class ValidationReviewRunDetailResponse(BaseModel):
    requestId: str
    artifact: ValidationReviewArtifact


class CreateValidationBaselineRequest(BaseModel):
    runId: str
    name: str = Field(min_length=1)
    notes: str | None = None


class ValidationBaseline(BaseModel):
    id: str
    runId: str
    name: str
    profile: ValidationProfile
    createdAt: str


class ValidationBaselineResponse(BaseModel):
    requestId: str
    baseline: ValidationBaseline


class CreateValidationRegressionReplayRequest(BaseModel):
    baselineId: str
    candidateRunId: str
    policyOverrides: dict[str, Any] = Field(default_factory=dict)


class ValidationRegressionReplay(BaseModel):
    id: str
    baselineId: str
    candidateRunId: str
    status: Literal["queued", "running", "completed", "failed"]
    decision: Literal["pass", "conditional_pass", "fail", "unknown"]
    mergeBlocked: bool
    releaseBlocked: bool
    mergeGateStatus: ValidationReplayGateStatus
    releaseGateStatus: ValidationReplayGateStatus
    baselineDecision: ValidationDecision
    candidateDecision: ValidationDecision
    metricDriftDeltaPct: float = Field(ge=0)
    metricDriftThresholdPct: float = Field(ge=0)
    thresholdBreached: bool
    reasons: list[str] = Field(default_factory=list)
    summary: str | None = None


class ValidationRegressionReplayResponse(BaseModel):
    requestId: str
    replay: ValidationRegressionReplay


BotStatus = Literal["active", "suspended", "revoked"]
BotRegistrationPath = Literal["invite_code_trial", "partner_bootstrap"]
BotKeyStatus = Literal["active", "rotated", "revoked"]
ValidationInviteStatus = Literal["pending", "accepted", "revoked", "expired"]
ValidationShareStatus = Literal["active", "revoked"]


class Bot(BaseModel):
    id: str
    tenantId: str
    ownerUserId: str
    name: str = Field(min_length=1)
    status: BotStatus
    registrationPath: BotRegistrationPath
    trialExpiresAt: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class BotKeyMetadata(BaseModel):
    id: str
    botId: str
    keyPrefix: str
    status: BotKeyStatus
    createdAt: str
    lastUsedAt: str | None = None
    revokedAt: str | None = None


class BotIssuedApiKey(BaseModel):
    rawKey: str = Field(min_length=16)
    key: BotKeyMetadata


class BotRegistration(BaseModel):
    id: str
    botId: str
    registrationPath: BotRegistrationPath
    status: Literal["completed"]
    audit: dict[str, Any] = Field(default_factory=dict)
    createdAt: str


class BotRegistrationResponse(BaseModel):
    requestId: str
    bot: Bot
    registration: BotRegistration
    issuedKey: BotIssuedApiKey


class CreateBotInviteRegistrationRequest(BaseModel):
    inviteCode: str = Field(min_length=8)
    botName: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateBotPartnerBootstrapRequest(BaseModel):
    partnerKey: str = Field(min_length=8)
    partnerSecret: str = Field(min_length=8)
    ownerEmail: str = Field(min_length=3, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    botName: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateBotKeyRotationRequest(BaseModel):
    reason: str | None = Field(default=None, min_length=1)


class BotKeyRotationResponse(BaseModel):
    requestId: str
    botId: str
    issuedKey: BotIssuedApiKey


class CreateBotKeyRevocationRequest(BaseModel):
    reason: str | None = Field(default=None, min_length=1)


class BotKeyMetadataResponse(BaseModel):
    requestId: str
    botId: str
    key: BotKeyMetadata


class ValidationInvite(BaseModel):
    id: str
    runId: str
    email: str
    status: ValidationInviteStatus
    invitedByUserId: str
    invitedByActorType: ValidationActorType
    createdAt: str
    expiresAt: str | None = None
    acceptedAt: str | None = None
    revokedAt: str | None = None


class ValidationRunShare(BaseModel):
    id: str
    runId: str
    ownerUserId: str
    sharedWithEmail: str
    sharedWithUserId: str | None = None
    inviteId: str | None = None
    status: ValidationShareStatus
    grantedAt: str
    revokedAt: str | None = None


class CreateValidationInviteRequest(BaseModel):
    email: str
    message: str | None = None
    expiresAt: str | None = None


class ValidationInviteResponse(BaseModel):
    requestId: str
    invite: ValidationInvite


class ValidationInviteListResponse(BaseModel):
    requestId: str
    items: list[ValidationInvite] = Field(default_factory=list)
    nextCursor: str | None = None


class AcceptValidationInviteRequest(BaseModel):
    acceptedEmail: str
    loginSessionId: str | None = Field(default=None, min_length=1)


class ValidationInviteAcceptanceResponse(BaseModel):
    requestId: str
    invite: ValidationInvite
    share: ValidationRunShare
