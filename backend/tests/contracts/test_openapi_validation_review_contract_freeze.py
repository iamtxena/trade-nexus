"""Freeze checks for the v2 validation-review web contract surface (#275)."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_SPEC = REPO_ROOT / "docs/architecture/specs/platform-api.openapi.yaml"

EXPECTED_REVIEW_PATHS = {
    "/v2/validation-review/runs",
    "/v2/validation-review/runs/{runId}",
    "/v2/validation-review/runs/{runId}/comments",
    "/v2/validation-review/runs/{runId}/decisions",
    "/v2/validation-review/runs/{runId}/renders",
    "/v2/validation-review/runs/{runId}/renders/{format}",
}

EXPECTED_REVIEW_OPERATION_IDS = {
    "listValidationReviewRunsV2",
    "getValidationReviewRunV2",
    "createValidationReviewCommentV2",
    "createValidationReviewDecisionV2",
    "createValidationReviewRenderV2",
    "getValidationReviewRenderV2",
}


def _spec_text() -> str:
    return OPENAPI_SPEC.read_text(encoding="utf-8")


def _path_block(spec: str, *, path: str) -> str:
    marker = f"  {path}:"
    return spec.split(marker, maxsplit=1)[1].split("\n  /", maxsplit=1)[0]


def test_validation_review_path_set_is_frozen() -> None:
    spec = _spec_text()
    discovered_paths = set(re.findall(r"^  (/v2/validation-review/.+):$", spec, flags=re.MULTILINE))
    assert discovered_paths == EXPECTED_REVIEW_PATHS


def test_validation_review_operation_ids_are_frozen() -> None:
    spec = _spec_text()
    operation_ids = set(re.findall(r"^\s+operationId:\s+([A-Za-z0-9_]+)\s*$", spec, flags=re.MULTILINE))
    review_ids = {operation_id for operation_id in operation_ids if "ValidationReview" in operation_id}
    assert review_ids == EXPECTED_REVIEW_OPERATION_IDS


def test_review_writes_require_idempotency_key() -> None:
    spec = _spec_text()
    required_header_ref = "$ref: '#/components/parameters/IdempotencyKey'"
    for path in (
        "/v2/validation-review/runs/{runId}/comments",
        "/v2/validation-review/runs/{runId}/decisions",
        "/v2/validation-review/runs/{runId}/renders",
    ):
        assert required_header_ref in _path_block(spec, path=path)


def test_review_decision_action_enum_is_frozen() -> None:
    spec = _spec_text()
    decision_action_block = spec.split("ValidationReviewDecisionAction:", maxsplit=1)[1].split(
        "ValidationReviewDecision:",
        maxsplit=1,
    )[0]
    assert "enum: [approve, reject]" in decision_action_block


def test_canonical_review_artifact_schema_is_frozen() -> None:
    spec = _spec_text()
    artifact_block = spec.split("ValidationReviewArtifact:", maxsplit=1)[1].split(
        "ValidationReviewRunDetailResponse:",
        maxsplit=1,
    )[0]
    for token in (
        "schemaVersion:",
        "enum: [validation-review.v1]",
        "run:",
        "artifact:",
        "comments:",
        "decision:",
        "renders:",
    ):
        assert token in artifact_block
