"""Contract tests for release replay gate preflight checks (#229)."""

from __future__ import annotations

import asyncio
import json

from src.platform_api.validation.release_gate_check import (
    compute_release_gate_replay,
    run_release_gate_check,
)


def test_release_gate_check_returns_pass_for_standard_candidate() -> None:
    replay = asyncio.run(compute_release_gate_replay())
    assert replay.status == "completed"
    assert replay.decision == "pass"
    assert replay.mergeBlocked is False
    assert replay.releaseBlocked is False
    assert replay.mergeGateStatus == "pass"
    assert replay.releaseGateStatus == "pass"


def test_release_gate_check_fails_for_blocked_candidate(tmp_path) -> None:
    output_file = tmp_path / "validation-release-gate.json"
    exit_code = run_release_gate_check(
        baseline_profile="STANDARD",
        candidate_profile="EXPERT",
        output_path=str(output_file),
    )
    assert exit_code == 1

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    assert payload["status"] == "completed"
    assert payload["decision"] == "fail"
    assert payload["mergeBlocked"] is True
    assert payload["releaseBlocked"] is True
    assert payload["mergeGateStatus"] == "blocked"
    assert payload["releaseGateStatus"] == "blocked"
