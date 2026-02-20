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
        "/v2/validation-baselines:",
        "/v2/validation-regressions/replay:",
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
        "createValidationBaselineV2",
        "replayValidationRegressionV2",
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
        "CreateValidationBaselineRequest:",
        "ValidationBaselineResponse:",
        "CreateValidationRegressionReplayRequest:",
        "ValidationRegressionReplayResponse:",
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
