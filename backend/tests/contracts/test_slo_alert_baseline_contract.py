"""Contract checks for Gate5 SLO/alert baseline governance (R-04)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_slo_alert_baseline_config_has_required_collections() -> None:
    config_path = _repo_root() / "contracts/config/slo-alert-baseline.v1.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    assert payload["baselineVersion"] == "gate5-slo-alert-baseline.v1"
    assert payload["ownerTeam"] == "Team F"
    assert isinstance(payload["slos"], list)
    assert len(payload["slos"]) >= 5
    assert isinstance(payload["alerts"], list)
    assert len(payload["alerts"]) >= 5


def test_slo_alert_baseline_config_covers_required_critical_paths_and_unique_ids() -> None:
    config_path = _repo_root() / "contracts/config/slo-alert-baseline.v1.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    required_paths = {"execution", "risk", "research", "reconciliation", "conversation"}
    covered_paths: set[str] = set()
    slo_ids: set[str] = set()
    alert_ids: set[str] = set()

    for slo in payload["slos"]:
        assert isinstance(slo["id"], str) and slo["id"].strip()
        assert slo["id"] not in slo_ids
        slo_ids.add(slo["id"])
        assert isinstance(slo["ownerTeam"], str) and slo["ownerTeam"].strip()
        critical_paths = {token.strip() for token in str(slo["criticalPath"]).split(",") if token.strip()}
        covered_paths.update(critical_paths)

    for alert in payload["alerts"]:
        assert isinstance(alert["id"], str) and alert["id"].strip()
        assert alert["id"] not in alert_ids
        alert_ids.add(alert["id"])
        assert isinstance(alert["ownerTeam"], str) and alert["ownerTeam"].strip()

    assert required_paths.issubset(covered_paths)


def test_slo_alert_baseline_docs_and_config_alignment_check_passes() -> None:
    script_path = _repo_root() / "contracts/scripts/check-slo-alert-baseline.py"
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
