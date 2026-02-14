"""Contract guardrails for OpenClaw client-lane boundaries (OC-01)."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
OPENCLAW_DOC = REPO_ROOT / "docs/architecture/OPENCLAW_INTEGRATION.md"
INTERFACES_DOC = REPO_ROOT / "docs/architecture/INTERFACES.md"
OPENAPI_SPEC = REPO_ROOT / "docs/architecture/specs/platform-api.openapi.yaml"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_openclaw_doc_exists_and_is_contract_focused() -> None:
    text = _text(OPENCLAW_DOC)

    required_tokens = (
        "OpenClaw is an external conversational client surface",
        "OpenClaw remains a **client lane only**",
        "OpenClaw must not call Lona, live-engine, or data providers directly",
        "Provider integrations are only allowed inside platform adapters",
        "OC-01 does **not** add OpenClaw-specific backend endpoints",
    )

    for token in required_tokens:
        assert token in text, f"Missing OpenClaw contract token: {token}"


def test_interfaces_doc_declares_openclaw_lane_rules() -> None:
    text = _text(INTERFACES_DOC)

    required_tokens = (
        "Public endpoints exposed to clients (CLI, web, OpenClaw, and other agents)",
        "### Client Lane Contract (OC-01)",
        "OpenClaw is a first-class **client lane**",
        "OpenClaw does not call provider APIs directly",
        "OpenClaw does not introduce dedicated `/v1/openclaw/*` endpoints",
    )

    for token in required_tokens:
        assert token in text, f"Missing interfaces token: {token}"


def test_openapi_has_no_openclaw_specific_v1_paths() -> None:
    spec_text = _text(OPENAPI_SPEC)
    assert "/v1/openclaw" not in spec_text
