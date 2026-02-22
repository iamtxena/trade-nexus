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
    "/v2/validation-review/runs",
    "/v2/validation-review/runs/{runId}",
    "/v2/validation-review/runs/{runId}/comments",
    "/v2/validation-review/runs/{runId}/decisions",
    "/v2/validation-review/runs/{runId}/renders",
    "/v2/validation-review/runs/{runId}/renders/{format}",
    "/v2/validation-baselines",
    "/v2/validation-regressions/replay",
    "/v2/validation-bots/registrations/invite-code",
    "/v2/validation-bots/registrations/partner-bootstrap",
    "/v2/validation-bots/{botId}/keys/rotate",
    "/v2/validation-bots/{botId}/keys/{keyId}/revoke",
    "/v2/validation-sharing/runs/{runId}/invites",
    "/v2/validation-sharing/invites/{inviteId}/revoke",
    "/v2/validation-sharing/invites/{inviteId}/accept",
}

EXPECTED_VALIDATION_V2_OPERATION_IDS = {
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
    "registerValidationBotInviteCodeV2",
    "registerValidationBotPartnerBootstrapV2",
    "rotateValidationBotKeyV2",
    "revokeValidationBotKeyV2",
    "listValidationRunInvitesV2",
    "createValidationRunInviteV2",
    "revokeValidationInviteV2",
    "acceptValidationInviteOnLoginV2",
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
        "createValidationReviewCommentV2",
        "createValidationReviewDecisionV2",
        "createValidationReviewRenderV2",
        "createValidationBaselineV2",
        "replayValidationRegressionV2",
        "registerValidationBotInviteCodeV2",
        "registerValidationBotPartnerBootstrapV2",
        "rotateValidationBotKeyV2",
        "revokeValidationBotKeyV2",
        "createValidationRunInviteV2",
        "revokeValidationInviteV2",
        "acceptValidationInviteOnLoginV2",
    ):
        block = _operation_block(spec, operation_id)
        assert "#/components/parameters/IdempotencyKey" in block


def test_validation_sharing_paths_stay_under_dedicated_surface() -> None:
    spec = _spec_text()
    sharing_paths = set(re.findall(r"^  (/v2/validation-sharing/.+):$", spec, flags=re.MULTILINE))
    assert sharing_paths == {
        "/v2/validation-sharing/runs/{runId}/invites",
        "/v2/validation-sharing/invites/{inviteId}/revoke",
        "/v2/validation-sharing/invites/{inviteId}/accept",
    }


def test_bot_key_metadata_never_declares_raw_key_field() -> None:
    spec = _spec_text()
    key_metadata_block = spec.split("BotKeyMetadata:", maxsplit=1)[1].split("BotIssuedApiKey:", maxsplit=1)[0]
    assert "rawKey" not in key_metadata_block

    issued_key_block = spec.split("BotIssuedApiKey:", maxsplit=1)[1].split("BotRegistration:", maxsplit=1)[0]
    assert "rawKey" in issued_key_block


def test_validation_actor_linkage_contract_stays_declared_on_run_and_artifact() -> None:
    spec = _spec_text()

    run_block = spec.split("ValidationRun:", maxsplit=1)[1].split("ValidationRunResponse:", maxsplit=1)[0]
    assert "actor:" in run_block
    assert "Runtime guarantees actor linkage on successful v2 responses." in run_block

    artifact_block = spec.split("ValidationRunArtifact:", maxsplit=1)[1].split(
        "ValidationSnapshotDeterministicChecks:",
        maxsplit=1,
    )[0]
    assert "actor:" in artifact_block
    assert "Runtime guarantees actor linkage on successful v2 responses." in artifact_block
