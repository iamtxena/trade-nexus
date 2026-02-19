"""Contract tests for replay comparison and merge/release gate policy evaluation (#229)."""

from __future__ import annotations

import pytest

from src.platform_api.services.validation_replay_policy import (
    ValidationReplayInputs,
    ci_gate_status,
    evaluate_replay_policy,
)


@pytest.mark.parametrize(
    (
        "baseline_decision",
        "candidate_decision",
        "baseline_drift",
        "candidate_drift",
        "threshold",
        "block_merge_on_fail",
        "block_release_on_fail",
        "block_merge_on_agent_fail",
        "block_release_on_agent_fail",
        "expected_decision",
        "expected_merge_blocked",
        "expected_release_blocked",
        "expected_reasons",
    ),
    [
        (
            "fail",
            "pass",
            0.8,
            0.2,
            0.5,
            True,
            True,
            True,
            False,
            "pass",
            False,
            False,
            (),
        ),
        (
            "pass",
            "fail",
            0.2,
            0.8,
            2.0,
            True,
            True,
            True,
            False,
            "fail",
            True,
            True,
            ("candidate_decision_regressed_from_baseline",),
        ),
        (
            "conditional_pass",
            "conditional_pass",
            0.2,
            0.3,
            1.0,
            True,
            True,
            True,
            False,
            "conditional_pass",
            True,
            False,
            (),
        ),
        (
            "pass",
            "pass",
            0.2,
            1.1,
            0.5,
            False,
            True,
            True,
            False,
            "fail",
            False,
            True,
            ("metric_drift_threshold_exceeded",),
        ),
    ],
)
def test_replay_policy_pass_fail_matrix(
    baseline_decision: str,
    candidate_decision: str,
    baseline_drift: float,
    candidate_drift: float,
    threshold: float,
    block_merge_on_fail: bool,
    block_release_on_fail: bool,
    block_merge_on_agent_fail: bool,
    block_release_on_agent_fail: bool,
    expected_decision: str,
    expected_merge_blocked: bool,
    expected_release_blocked: bool,
    expected_reasons: tuple[str, ...],
) -> None:
    outcome = evaluate_replay_policy(
        inputs=ValidationReplayInputs(
            baseline_decision=baseline_decision,  # type: ignore[arg-type]
            candidate_decision=candidate_decision,  # type: ignore[arg-type]
            baseline_metric_drift_pct=baseline_drift,
            candidate_metric_drift_pct=candidate_drift,
            metric_drift_threshold_pct=threshold,
            block_merge_on_fail=block_merge_on_fail,
            block_release_on_fail=block_release_on_fail,
            block_merge_on_agent_fail=block_merge_on_agent_fail,
            block_release_on_agent_fail=block_release_on_agent_fail,
        )
    )

    assert outcome.decision == expected_decision
    assert outcome.merge_blocked is expected_merge_blocked
    assert outcome.release_blocked is expected_release_blocked
    assert outcome.reasons == expected_reasons


def test_replay_policy_threshold_behavior_is_strictly_greater_than() -> None:
    at_threshold = evaluate_replay_policy(
        inputs=ValidationReplayInputs(
            baseline_decision="pass",
            candidate_decision="pass",
            baseline_metric_drift_pct=0.2,
            candidate_metric_drift_pct=0.7,
            metric_drift_threshold_pct=0.5,
            block_merge_on_fail=True,
            block_release_on_fail=True,
            block_merge_on_agent_fail=True,
            block_release_on_agent_fail=False,
        )
    )
    assert at_threshold.threshold_breached is False
    assert at_threshold.decision == "pass"

    over_threshold = evaluate_replay_policy(
        inputs=ValidationReplayInputs(
            baseline_decision="pass",
            candidate_decision="pass",
            baseline_metric_drift_pct=0.2,
            candidate_metric_drift_pct=0.700001,
            metric_drift_threshold_pct=0.5,
            block_merge_on_fail=True,
            block_release_on_fail=True,
            block_merge_on_agent_fail=True,
            block_release_on_agent_fail=False,
        )
    )
    assert over_threshold.threshold_breached is True
    assert over_threshold.decision == "fail"
    assert "metric_drift_threshold_exceeded" in over_threshold.reasons


def test_replay_policy_ci_gate_behavior_reflects_blocking_flags() -> None:
    outcome = evaluate_replay_policy(
        inputs=ValidationReplayInputs(
            baseline_decision="pass",
            candidate_decision="pass",
            baseline_metric_drift_pct=0.1,
            candidate_metric_drift_pct=1.1,
            metric_drift_threshold_pct=0.5,
            block_merge_on_fail=False,
            block_release_on_fail=True,
            block_merge_on_agent_fail=True,
            block_release_on_agent_fail=False,
        )
    )
    assert outcome.decision == "fail"
    assert ci_gate_status(outcome=outcome, gate="merge") == "pass"
    assert ci_gate_status(outcome=outcome, gate="release") == "blocked"
    with pytest.raises(ValueError):
        ci_gate_status(outcome=outcome, gate="deploy")  # type: ignore[arg-type]

