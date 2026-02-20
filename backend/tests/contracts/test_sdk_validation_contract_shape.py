"""Contract checks for generated SDK validation surface (#224, #223)."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SDK_API = REPO_ROOT / "sdk/typescript/src/apis/ValidationApi.ts"
SDK_MODELS = REPO_ROOT / "sdk/typescript/src/models"
SDK_INDEX = REPO_ROOT / "sdk/typescript/src/models/index.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_validation_api_is_generated_with_all_validation_operations() -> None:
    api = _read(SDK_API)
    for operation in (
        "listValidationRunsV2(",
        "createValidationRunV2(",
        "getValidationRunV2(",
        "getValidationRunArtifactV2(",
        "submitValidationRunReviewV2(",
        "createValidationRunRenderV2(",
        "createValidationBaselineV2(",
        "replayValidationRegressionV2(",
    ):
        assert operation in api, f"Missing SDK validation operation: {operation}"


def test_validation_policy_model_exposes_frozen_profile_and_blocking_flags() -> None:
    policy_model = _read(SDK_MODELS / "ValidationPolicyProfile.ts")
    for token in (
        "profile: ValidationProfile;",
        "blockMergeOnFail: boolean;",
        "blockReleaseOnFail: boolean;",
        "blockMergeOnAgentFail: boolean;",
        "blockReleaseOnAgentFail: boolean;",
        "requireTraderReview: boolean;",
        "hardFailOnMissingIndicators: boolean;",
        "failClosedOnEvidenceUnavailable: boolean;",
    ):
        assert token in policy_model


def test_validation_artifact_models_are_exported() -> None:
    index = _read(SDK_INDEX)
    for model in (
        "ValidationRunListResponse",
        "ValidationRunArtifact",
        "ValidationLlmSnapshotArtifact",
        "ValidationArtifactResponse",
        "ValidationRunResponse",
    ):
        assert f"export * from './{model}';" in index


def test_validation_write_request_types_expose_idempotency_key() -> None:
    api = _read(SDK_API)
    for request_type in (
        "CreateValidationRunV2Request",
        "SubmitValidationRunReviewV2Request",
        "CreateValidationRunRenderV2Request",
        "CreateValidationBaselineV2Request",
        "ReplayValidationRegressionV2Request",
    ):
        request_block = api.split(f"export interface {request_type}", maxsplit=1)[1].split(
            "}\n",
            maxsplit=1,
        )[0]
        assert "idempotencyKey: string;" in request_block
