"""Contract checks for generated SDK validation-review surface (#275)."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SDK_API = REPO_ROOT / "sdk/typescript/src/apis/ValidationApi.ts"
SDK_MODELS_INDEX = REPO_ROOT / "sdk/typescript/src/models/index.ts"
SDK_MODEL_DIR = REPO_ROOT / "sdk/typescript/src/models"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_validation_review_api_methods_are_generated() -> None:
    api = _read(SDK_API)
    for operation in (
        "listValidationReviewRunsV2(",
        "getValidationReviewRunV2(",
        "createValidationReviewCommentV2(",
        "createValidationReviewDecisionV2(",
        "createValidationReviewRenderV2(",
        "getValidationReviewRenderV2(",
    ):
        assert operation in api, f"Missing SDK validation-review operation: {operation}"


def test_validation_review_model_exports_are_generated() -> None:
    index = _read(SDK_MODELS_INDEX)
    for model in (
        "ValidationReviewArtifact",
        "ValidationReviewComment",
        "ValidationReviewCommentResponse",
        "ValidationReviewDecision",
        "ValidationReviewDecisionAction",
        "ValidationReviewDecisionResponse",
        "ValidationReviewRenderJob",
        "ValidationReviewRenderResponse",
        "ValidationReviewRunDetailResponse",
        "ValidationReviewRunListResponse",
        "ValidationReviewRunSummary",
    ):
        assert f"export * from './{model}';" in index


def test_validation_review_canonical_schema_version_is_exposed() -> None:
    review_artifact_model = _read(SDK_MODEL_DIR / "ValidationReviewArtifact.ts")
    assert "validation-review.v1" in review_artifact_model
