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
    assert "--output .ops/artifacts/validation-replay-gate-contracts-governance.json" in workflow
    assert "name: upload replay gate report (merge governance)" in workflow
    assert "uses: actions/upload-artifact@v4" in workflow
    assert "name: validation-replay-gate-contracts-governance" in workflow

    preflight_idx = workflow.index("name: enforce replay gate preflight for merge-time governance")
    upload_idx = workflow.index("name: upload replay gate report (merge governance)")
    assert preflight_idx < upload_idx


def test_backend_deploy_enforces_replay_gate_preflight() -> None:
    workflow = _workflow_text(BACKEND_DEPLOY_WORKFLOW)
    assert "python -m src.platform_api.validation.release_gate_check" in workflow
    assert "--output /workspace/.ops/artifacts/validation-replay-gate-backend-deploy.json" in workflow
    assert "name: upload replay gate report (release deploy)" in workflow
    assert "uses: actions/upload-artifact@v4" in workflow
    assert "name: validation-replay-gate-backend-deploy" in workflow
