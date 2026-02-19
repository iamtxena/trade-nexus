"""Contract checks for replay gate CI enforcement paths (#261)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS_GOVERNANCE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "contracts-governance.yml"
BACKEND_DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "backend-deploy.yml"


def _workflow_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_contracts_governance_enforces_replay_gate_preflight() -> None:
    workflow = _workflow_text(CONTRACTS_GOVERNANCE_WORKFLOW)
    assert "name: enforce replay gate preflight for merge-time governance" in workflow
    assert "python -m src.platform_api.validation.release_gate_check" in workflow

    preflight_idx = workflow.index("name: enforce replay gate preflight for merge-time governance")
    backend_tests_idx = workflow.index("name: run backend contract behavior tests")
    assert preflight_idx < backend_tests_idx


def test_backend_deploy_enforces_replay_gate_preflight() -> None:
    workflow = _workflow_text(BACKEND_DEPLOY_WORKFLOW)
    assert "python -m src.platform_api.validation.release_gate_check" in workflow
