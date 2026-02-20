"""Contract tests for release replay gate preflight checks (#229)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from src.platform_api.validation.release_gate_check import (
    build_release_gate_report,
    compute_release_gate_replay,
    run_release_gate_check,
)
from tests.contracts.test_validation_schema_contract import (
    _load_schema,
    _validate_against_schema,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATION_REPLAY_GATE_REPORT_SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "schemas" / "validation_replay_gate_report.json"
)


def test_release_gate_check_returns_pass_for_standard_candidate() -> None:
    replay = asyncio.run(compute_release_gate_replay())
    assert replay.status == "completed"
    assert replay.decision == "pass"
    assert replay.mergeBlocked is False
    assert replay.releaseBlocked is False
    assert replay.mergeGateStatus == "pass"
    assert replay.releaseGateStatus == "pass"

    report = build_release_gate_report(replay=replay)
    schema = _load_schema(VALIDATION_REPLAY_GATE_REPORT_SCHEMA_PATH)
    _validate_against_schema(report, schema)
    assert report["gateStatus"] == "pass"
    assert report["gate"]["status"] == "completed"


def test_release_gate_check_fails_for_blocked_candidate(tmp_path) -> None:
    output_file = tmp_path / "validation-release-gate.json"
    exit_code = run_release_gate_check(
        baseline_profile="STANDARD",
        candidate_profile="EXPERT",
        output_path=str(output_file),
    )
    assert exit_code == 1

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    schema = _load_schema(VALIDATION_REPLAY_GATE_REPORT_SCHEMA_PATH)
    _validate_against_schema(payload, schema)

    assert payload["schemaVersion"] == "validation-replay-gate-report.v1"
    assert payload["gateStatus"] == "blocked"
    assert payload["gate"]["status"] == "completed"
    assert payload["gate"]["decision"] == "fail"
    assert payload["gate"]["mergeBlocked"] is True
    assert payload["gate"]["releaseBlocked"] is True
    assert payload["gate"]["mergeGateStatus"] == "blocked"
    assert payload["gate"]["releaseGateStatus"] == "blocked"
    assert [entry["kind"] for entry in payload["evidenceRefs"]] == [
        "validation_replay_id",
        "validation_baseline_id",
        "validation_candidate_run_id",
    ]


def test_release_gate_report_schema_accepts_nullable_summary() -> None:
    replay = asyncio.run(compute_release_gate_replay())
    replay_with_null_summary = replay.model_copy(update={"summary": None})
    report = build_release_gate_report(replay=replay_with_null_summary)

    schema = _load_schema(VALIDATION_REPLAY_GATE_REPORT_SCHEMA_PATH)
    _validate_against_schema(report, schema)
    assert report["gate"]["summary"] is None
