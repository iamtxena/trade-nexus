"""Baseline governance checks for the canonical OpenAPI contract.

These tests intentionally validate a stable subset of architecture rules without
parsing provider-specific implementation details.
"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
OPENAPI_SPEC = REPO_ROOT / "docs/architecture/specs/platform-api.openapi.yaml"


def _spec_text() -> str:
    return OPENAPI_SPEC.read_text(encoding="utf-8")


def test_openapi_file_exists() -> None:
    assert OPENAPI_SPEC.exists(), "Canonical OpenAPI file is missing."


def test_versioned_platform_paths_are_present() -> None:
    spec = _spec_text()
    for path in (
        "/v1/health:",
        "/v1/research/market-scan:",
        "/v1/strategies:",
        "/v1/backtests/{backtestId}:",
        "/v1/deployments:",
        "/v1/portfolios:",
        "/v1/orders:",
        "/v1/datasets/uploads:init:",
        "/v1/datasets/{datasetId}/uploads:complete:",
        "/v1/datasets/{datasetId}/validate:",
        "/v1/datasets/{datasetId}/transform/candles:",
        "/v1/datasets/{datasetId}/publish/lona:",
        "/v1/datasets:",
        "/v1/datasets/{datasetId}:",
        "/v1/datasets/{datasetId}/quality-report:",
    ):
        assert path in spec, f"Missing required path in OpenAPI: {path}"


def test_idempotency_header_required_on_side_effecting_posts() -> None:
    spec = _spec_text()
    required_header_ref = "$ref: '#/components/parameters/IdempotencyKey'"

    deployment_block = spec.split("/v1/deployments:")[1].split("/v1/")[0]
    order_block = spec.split("/v1/orders:")[1]

    assert required_header_ref in deployment_block
    assert required_header_ref in order_block


def test_error_envelope_is_defined() -> None:
    spec = _spec_text()
    assert "ErrorResponse:" in spec
    assert "requestId:" in spec
    assert "error:" in spec


def test_public_tags_are_declared() -> None:
    spec = _spec_text()
    for tag in (
        "name: Health",
        "name: Research",
        "name: Strategies",
        "name: Backtests",
        "name: Deployments",
        "name: Portfolios",
        "name: Orders",
        "name: Datasets",
    ):
        assert tag in spec, f"Missing expected tag declaration: {tag}"
