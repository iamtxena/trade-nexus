"""Replay comparison and policy gate evaluation for validation regression checks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


ValidationDecision = Literal["pass", "conditional_pass", "fail"]
ValidationReplayDecision = Literal["pass", "conditional_pass", "fail", "unknown"]
ValidationReplayGateStatus = Literal["pass", "blocked"]
ValidationReplayGate = Literal["merge", "release"]

_DECISION_RANK: dict[ValidationDecision, int] = {
    "fail": 0,
    "conditional_pass": 1,
    "pass": 2,
}


@dataclass(frozen=True)
class ValidationReplayInputs:
    baseline_decision: ValidationDecision
    candidate_decision: ValidationDecision
    baseline_metric_drift_pct: float
    candidate_metric_drift_pct: float
    metric_drift_threshold_pct: float
    block_merge_on_fail: bool
    block_release_on_fail: bool
    block_merge_on_agent_fail: bool
    block_release_on_agent_fail: bool


@dataclass(frozen=True)
class ValidationReplayOutcome:
    decision: ValidationReplayDecision
    merge_blocked: bool
    release_blocked: bool
    merge_gate_status: ValidationReplayGateStatus
    release_gate_status: ValidationReplayGateStatus
    baseline_decision: ValidationDecision
    candidate_decision: ValidationDecision
    metric_drift_delta_pct: float
    metric_drift_threshold_pct: float
    threshold_breached: bool
    reasons: tuple[str, ...]


def _to_non_negative_finite(value: float, *, field_name: str) -> float:
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    if normalized < 0:
        raise ValueError(f"{field_name} must be >= 0.")
    return normalized


def ci_gate_status(*, outcome: ValidationReplayOutcome, gate: ValidationReplayGate) -> ValidationReplayGateStatus:
    if gate == "merge":
        return "blocked" if outcome.merge_blocked else "pass"
    if gate == "release":
        return "blocked" if outcome.release_blocked else "pass"
    raise ValueError(f"Unsupported replay gate: {gate!r}")


def evaluate_replay_policy(*, inputs: ValidationReplayInputs) -> ValidationReplayOutcome:
    baseline_metric_drift_pct = _to_non_negative_finite(
        inputs.baseline_metric_drift_pct,
        field_name="baseline_metric_drift_pct",
    )
    candidate_metric_drift_pct = _to_non_negative_finite(
        inputs.candidate_metric_drift_pct,
        field_name="candidate_metric_drift_pct",
    )
    metric_drift_threshold_pct = _to_non_negative_finite(
        inputs.metric_drift_threshold_pct,
        field_name="metric_drift_threshold_pct",
    )

    candidate_rank = _DECISION_RANK[inputs.candidate_decision]
    baseline_rank = _DECISION_RANK[inputs.baseline_decision]
    decision: ValidationReplayDecision = inputs.candidate_decision
    reasons: list[str] = []

    if candidate_rank < baseline_rank:
        decision = "fail"
        reasons.append("candidate_decision_regressed_from_baseline")

    # Replay threshold focuses on regression drift from baseline; candidate improvements do not breach.
    metric_drift_delta_pct = max(0.0, candidate_metric_drift_pct - baseline_metric_drift_pct)
    threshold_breached = metric_drift_delta_pct > metric_drift_threshold_pct
    if threshold_breached:
        decision = "fail"
        reasons.append("metric_drift_threshold_exceeded")

    merge_blocked = False
    release_blocked = False
    if decision == "fail":
        merge_blocked = inputs.block_merge_on_fail
        release_blocked = inputs.block_release_on_fail
    elif decision == "conditional_pass":
        merge_blocked = inputs.block_merge_on_agent_fail
        release_blocked = inputs.block_release_on_agent_fail

    return ValidationReplayOutcome(
        decision=decision,
        merge_blocked=merge_blocked,
        release_blocked=release_blocked,
        merge_gate_status="blocked" if merge_blocked else "pass",
        release_gate_status="blocked" if release_blocked else "pass",
        baseline_decision=inputs.baseline_decision,
        candidate_decision=inputs.candidate_decision,
        metric_drift_delta_pct=metric_drift_delta_pct,
        metric_drift_threshold_pct=metric_drift_threshold_pct,
        threshold_breached=threshold_breached,
        reasons=tuple(reasons),
    )


__all__ = [
    "ValidationReplayGate",
    "ValidationReplayGateStatus",
    "ValidationReplayInputs",
    "ValidationReplayOutcome",
    "evaluate_replay_policy",
    "ci_gate_status",
]
