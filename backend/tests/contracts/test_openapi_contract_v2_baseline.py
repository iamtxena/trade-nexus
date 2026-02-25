"""Baseline checks for additive /v2 KB/Data contract surface."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_SPEC = REPO_ROOT / "docs/architecture/specs/platform-api.openapi.yaml"


def _spec_text() -> str:
    return OPENAPI_SPEC.read_text(encoding="utf-8")


def test_v2_paths_are_declared() -> None:
    spec = _spec_text()
    for path in (
        "/v2/knowledge/search:",
        "/v2/knowledge/patterns:",
        "/v2/knowledge/regimes/{asset}:",
        "/v2/data/exports/backtest:",
        "/v2/data/exports/{exportId}:",
        "/v2/research/market-scan:",
        "/v2/conversations/sessions:",
        "/v2/conversations/sessions/{sessionId}:",
        "/v2/conversations/sessions/{sessionId}/turns:",
        "/v2/validation-runs:",
        "/v2/validation-runs/{runId}:",
        "/v2/validation-runs/{runId}/artifact:",
        "/v2/validation-runs/{runId}/review:",
        "/v2/validation-runs/{runId}/render:",
        "/v2/validation-review/runs:",
        "/v2/validation-review/runs/{runId}:",
        "/v2/validation-review/runs/{runId}/comments:",
        "/v2/validation-review/runs/{runId}/decisions:",
        "/v2/validation-review/runs/{runId}/renders:",
        "/v2/validation-review/runs/{runId}/renders/{format}:",
        "/v2/validation-baselines:",
        "/v2/validation-regressions/replay:",
        "/v2/validation-bots:",
        "/v2/validation-bots/registrations/invite-code:",
        "/v2/validation-bots/registrations/partner-bootstrap:",
        "/v2/validation-bots/{botId}/keys/rotate:",
        "/v2/validation-bots/{botId}/keys/{keyId}/revoke:",
        "/v2/validation-sharing/runs/shared-with-me:",
        "/v2/validation-sharing/runs/{runId}/invites:",
        "/v2/validation-sharing/invites/{inviteId}/revoke:",
        "/v2/validation-sharing/invites/{inviteId}/accept:",
    ):
        assert path in spec, f"Missing required v2 path: {path}"


def test_v2_operation_ids_are_declared() -> None:
    spec = _spec_text()
    for operation_id in (
        "searchKnowledgeV2",
        "listKnowledgePatternsV2",
        "getKnowledgeRegimeV2",
        "createBacktestDataExportV2",
        "getBacktestDataExportV2",
        "postMarketScanV2",
        "createConversationSessionV2",
        "getConversationSessionV2",
        "createConversationTurnV2",
        "listValidationRunsV2",
        "createValidationRunV2",
        "getValidationRunV2",
        "getValidationRunArtifactV2",
        "submitValidationRunReviewV2",
        "createValidationRunRenderV2",
        "listValidationReviewRunsV2",
        "getValidationReviewRunV2",
        "createValidationReviewCommentV2",
        "createValidationReviewDecisionV2",
        "createValidationReviewRenderV2",
        "getValidationReviewRenderV2",
        "createValidationBaselineV2",
        "replayValidationRegressionV2",
        "listValidationBotsV2",
        "registerValidationBotInviteCodeV2",
        "registerValidationBotPartnerBootstrapV2",
        "rotateValidationBotKeyV2",
        "revokeValidationBotKeyV2",
        "listValidationRunsSharedWithMeV2",
        "listValidationRunInvitesV2",
        "createValidationRunInviteV2",
        "revokeValidationInviteV2",
        "acceptValidationInviteOnLoginV2",
    ):
        assert f"operationId: {operation_id}" in spec


def test_v2_schema_components_are_present() -> None:
    spec = _spec_text()
    for component in (
        "KnowledgeSearchRequest:",
        "KnowledgeSearchResponse:",
        "KnowledgePattern:",
        "KnowledgeRegimeResponse:",
        "BacktestDataExportRequest:",
        "BacktestDataExportResponse:",
        "MarketScanV2Response:",
        "CreateConversationSessionRequest:",
        "ConversationSessionResponse:",
        "CreateConversationTurnRequest:",
        "ConversationTurnResponse:",
        "ValidationProfile:",
        "ValidationPolicyProfile:",
        "ValidationRunArtifact:",
        "ValidationLlmSnapshotArtifact:",
        "CreateValidationRunRequest:",
        "ValidationRunListResponse:",
        "ValidationRunResponse:",
        "ValidationArtifactResponse:",
        "CreateValidationRunReviewRequest:",
        "ValidationRunReviewResponse:",
        "CreateValidationRenderRequest:",
        "ValidationRenderResponse:",
        "ValidationReviewRunSummary:",
        "ValidationReviewRunListResponse:",
        "ValidationReviewComment:",
        "CreateValidationReviewCommentRequest:",
        "ValidationReviewCommentResponse:",
        "ValidationReviewDecisionAction:",
        "ValidationReviewDecision:",
        "CreateValidationReviewDecisionRequest:",
        "ValidationReviewDecisionResponse:",
        "CreateValidationReviewRenderRequest:",
        "ValidationReviewRenderJob:",
        "ValidationReviewRenderResponse:",
        "ValidationReviewArtifact:",
        "ValidationReviewRunDetailResponse:",
        "CreateValidationBaselineRequest:",
        "ValidationBaselineResponse:",
        "CreateValidationRegressionReplayRequest:",
        "ValidationRegressionReplayResponse:",
        "ValidationRunActorMetadata:",
        "Bot:",
        "BotSummary:",
        "BotUsageMetadata:",
        "BotListResponse:",
        "BotRegistration:",
        "BotKeyMetadata:",
        "ValidationSharePermission:",
        "ValidationRunShare:",
        "ValidationInvite:",
        "CreateBotInviteRegistrationRequest:",
        "CreateBotPartnerBootstrapRequest:",
        "CreateValidationInviteRequest:",
        "AcceptValidationInviteRequest:",
        "BotRegistrationResponse:",
        "ValidationInviteResponse:",
        "ValidationInviteListResponse:",
        "ValidationInviteAcceptanceResponse:",
        "ValidationSharedRunSummary:",
        "ValidationSharedRunListResponse:",
    ):
        assert component in spec


def test_validation_replay_schema_declares_gate_and_threshold_fields() -> None:
    spec = _spec_text()
    replay_component = spec.split("ValidationRegressionReplay:", maxsplit=1)[1].split(
        "ValidationRegressionReplayResponse:",
        maxsplit=1,
    )[0]
    for token in (
        "mergeBlocked",
        "releaseBlocked",
        "mergeGateStatus",
        "releaseGateStatus",
        "baselineDecision",
        "candidateDecision",
        "metricDriftDeltaPct",
        "metricDriftThresholdPct",
        "thresholdBreached",
        "reasons",
    ):
        assert token in replay_component


def test_validation_identity_and_sharing_non_negotiables_are_declared() -> None:
    spec = _spec_text()

    bot_component = spec.split("Bot:", maxsplit=1)[1].split("BotKeyMetadata:", maxsplit=1)[0]
    assert "ownerUserId:" in bot_component
    assert "brandId" not in bot_component
    assert "brand:" not in bot_component

    invite_create_component = spec.split("CreateValidationInviteRequest:", maxsplit=1)[1].split(
        "ValidationInviteResponse:",
        maxsplit=1,
    )[0]
    assert "email:" in invite_create_component
    assert "permission:" in invite_create_component
    assert "userId" not in invite_create_component

    invite_registration_path_block = spec.split(
        "operationId: registerValidationBotInviteCodeV2",
        maxsplit=1,
    )[1].split("operationId: registerValidationBotPartnerBootstrapV2", maxsplit=1)[0]
    assert "$ref: '#/components/responses/Error429'" in invite_registration_path_block

    partner_registration_path_block = spec.split(
        "operationId: registerValidationBotPartnerBootstrapV2",
        maxsplit=1,
    )[1].split("operationId: rotateValidationBotKeyV2", maxsplit=1)[0]
    assert "partnerKey" in partner_registration_path_block
    assert "partnerSecret" in partner_registration_path_block

    validation_run_block = spec.split("ValidationRun:", maxsplit=1)[1].split("ValidationRunResponse:", maxsplit=1)[0]
    assert "actor:" in validation_run_block
    assert "ValidationRunActorMetadata" in validation_run_block
