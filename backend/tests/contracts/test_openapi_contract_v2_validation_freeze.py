"""Freeze checks for additive /v2 validation contract surface (#224, #223)."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_SPEC = REPO_ROOT / "docs/architecture/specs/platform-api.openapi.yaml"

EXPECTED_VALIDATION_V2_PATHS = {
    "/v2/validation-runs",
    "/v2/validation-runs/{runId}",
    "/v2/validation-runs/{runId}/artifact",
    "/v2/validation-runs/{runId}/review",
    "/v2/validation-runs/{runId}/render",
    "/v2/validation-baselines",
    "/v2/validation-regressions/replay",
}

EXPECTED_VALIDATION_V2_OPERATION_IDS = {
    "listValidationRunsV2",
    "createValidationRunV2",
    "getValidationRunV2",
    "getValidationRunArtifactV2",
    "submitValidationRunReviewV2",
    "createValidationRunRenderV2",
    "createValidationBaselineV2",
    "replayValidationRegressionV2",
}


def _spec_text() -> str:
    return OPENAPI_SPEC.read_text(encoding="utf-8")


def _operation_block(spec: str, operation_id: str) -> str:
    return spec.split(f"operationId: {operation_id}", maxsplit=1)[1].split(
        "\n      responses:",
        maxsplit=1,
    )[0]


def test_validation_v2_path_set_is_frozen() -> None:
    spec = _spec_text()
    discovered_paths = set(re.findall(r"^  (/v2/validation[^:]*):$", spec, flags=re.MULTILINE))
    assert discovered_paths == EXPECTED_VALIDATION_V2_PATHS


def test_validation_v2_operation_ids_are_frozen() -> None:
    spec = _spec_text()
    operation_ids = set(re.findall(r"^\s+operationId:\s+([A-Za-z0-9_]+)\s*$", spec, flags=re.MULTILINE))
    discovered_validation_operation_ids = {
        name for name in operation_ids if "Validation" in name or name == "replayValidationRegressionV2"
    }
    assert discovered_validation_operation_ids == EXPECTED_VALIDATION_V2_OPERATION_IDS


def test_validation_contract_is_json_first_with_optional_html_pdf_render_only() -> None:
    spec = _spec_text()
    render_format_component = spec.split("ValidationRenderFormat:", maxsplit=1)[1].split(
        "CreateValidationRenderRequest:",
        maxsplit=1,
    )[0]
    assert "enum: [html, pdf]" in render_format_component
    assert "enum: [html, pdf, json]" not in render_format_component
    assert "ValidationArtifactResponse:" in spec


def test_validation_v2_write_operations_reference_idempotency_parameter() -> None:
    spec = _spec_text()
    for operation_id in (
        "createValidationRunV2",
        "submitValidationRunReviewV2",
        "createValidationRunRenderV2",
        "createValidationBaselineV2",
        "replayValidationRegressionV2",
    ):
        block = _operation_block(spec, operation_id)
        assert "#/components/parameters/IdempotencyKey" in block
