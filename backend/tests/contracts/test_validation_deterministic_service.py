"""Contract tests for V-02 deterministic validation engine."""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.platform_api.validation.core.agent_review import ValidationAgentReviewService
from src.platform_api.services.validation_deterministic_service import (
    DeterministicValidationEngine,
    DeterministicValidationEvidence,
    ValidationArtifactContext,
    ValidationPolicyConfig,
)
from tests.contracts.test_validation_schema_contract import (
    VALIDATION_RUN_SCHEMA_PATH,
    _load_schema,
    _validate_against_schema,
)


def _policy(*, tolerance_pct: float = 1.0) -> ValidationPolicyConfig:
    return ValidationPolicyConfig(metric_drift_tolerance_pct=tolerance_pct)


def _base_evidence() -> DeterministicValidationEvidence:
    return DeterministicValidationEvidence(
        requested_indicators=("zigzag", "ema"),
        rendered_indicators=("ema", "zigzag"),
        chart_payload={"indicators": [{"name": "ema"}, {"name": "zigzag"}]},
        trades=(
            {
                "id": "trade-001",
                "orderId": "ord-001",
            },
        ),
        execution_logs=(
            {"orderId": "ord-001", "status": "created"},
            {"orderId": "ord-001", "status": "accepted"},
            {"orderId": "ord-001", "status": "filled"},
        ),
        reported_metrics={
            "sharpeRatio": 1.50,
            "maxDrawdownPct": 9.00,
        },
        recomputed_metrics={
            "sharpeRatio": 1.49,
            "maxDrawdownPct": 9.05,
        },
        dataset_ids=("dataset-btc-1h-2025",),
        lineage={
            "datasets": [
                {
                    "datasetId": "dataset-btc-1h-2025",
                    "sourceRef": "blob://datasets/raw/btc.csv",
                }
            ]
        },
    )


def test_indicator_fidelity_check_passes_when_all_requested_indicators_are_rendered() -> None:
    engine = DeterministicValidationEngine()
    result = engine.check_indicator_fidelity(evidence=_base_evidence(), policy=_policy())
    assert result.status == "pass"
    assert result.missing_indicators == ()


def test_indicator_fidelity_check_fails_when_required_indicator_is_missing() -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        rendered_indicators=("ema",),
        chart_payload={"indicators": [{"name": "ema"}]},
    )
    result = engine.check_indicator_fidelity(evidence=evidence, policy=_policy())
    assert result.status == "fail"
    assert result.missing_indicators == ("zigzag",)


def test_trade_coherence_check_passes_for_valid_lifecycle_and_trade_reconciliation() -> None:
    engine = DeterministicValidationEngine()
    result = engine.check_trade_coherence(evidence=_base_evidence(), policy=_policy())
    assert result.status == "pass"
    assert result.violations == ()


def test_trade_coherence_check_fails_for_invalid_lifecycle_transition() -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        execution_logs=(
            {"orderId": "ord-001", "status": "created"},
            {"orderId": "ord-001", "status": "filled"},
            {"orderId": "ord-001", "status": "accepted"},
        ),
    )
    result = engine.check_trade_coherence(evidence=evidence, policy=_policy())
    assert result.status == "fail"
    assert any(item.startswith("invalid_lifecycle_transition:ord-001") for item in result.violations)


def test_trade_coherence_check_does_not_fuzzily_map_unrelated_state_substrings() -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        execution_logs=(
            {"orderId": "ord-001", "status": "created"},
            {"orderId": "ord-001", "status": "unfilled"},
            {"orderId": "ord-001", "status": "filled"},
        ),
    )
    result = engine.check_trade_coherence(evidence=evidence, policy=_policy())
    assert result.status == "fail"
    assert "execution_log_unknown_state:ord-001" in result.violations


def test_trade_coherence_check_treats_pending_states_as_unknown() -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        execution_logs=(
            {"orderId": "ord-001", "status": "created"},
            {"orderId": "ord-001", "status": "pending_cancel"},
            {"orderId": "ord-001", "status": "filled"},
        ),
    )
    result = engine.check_trade_coherence(evidence=evidence, policy=_policy())
    assert result.status == "fail"
    assert "execution_log_unknown_state:ord-001" in result.violations


@pytest.mark.parametrize("state", ["not_filled", "not_accepted", "non_filled"])
def test_trade_coherence_check_treats_negated_states_as_unknown(state: str) -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        execution_logs=(
            {"orderId": "ord-001", "status": "created"},
            {"orderId": "ord-001", "status": state},
            {"orderId": "ord-001", "status": "filled"},
        ),
    )
    result = engine.check_trade_coherence(evidence=evidence, policy=_policy())
    assert result.status == "fail"
    assert "execution_log_unknown_state:ord-001" in result.violations


def test_trade_coherence_check_uses_state_when_status_is_whitespace() -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        execution_logs=(
            {"orderId": "ord-001", "status": "   ", "state": "created"},
            {"orderId": "ord-001", "status": "accepted"},
            {"orderId": "ord-001", "status": "filled"},
        ),
    )
    result = engine.check_trade_coherence(evidence=evidence, policy=_policy())
    assert result.status == "pass"
    assert result.violations == ()


def test_metric_consistency_check_passes_within_policy_tolerance() -> None:
    engine = DeterministicValidationEngine()
    result = engine.check_metric_consistency(evidence=_base_evidence(), policy=_policy(tolerance_pct=1.0))
    assert result.status == "pass"
    assert result.drift_pct <= 1.0
    assert result.mismatches == ()


def test_metric_consistency_check_fails_when_drift_exceeds_policy_tolerance() -> None:
    engine = DeterministicValidationEngine()
    result = engine.check_metric_consistency(evidence=_base_evidence(), policy=_policy(tolerance_pct=0.5))
    assert result.status == "fail"
    assert result.drift_pct > 0.5
    assert any(item.startswith("metric_drift_exceeds_tolerance") for item in result.mismatches)


def test_metric_consistency_check_fails_closed_on_non_finite_values() -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        reported_metrics={
            "sharpeRatio": float("nan"),
            "maxDrawdownPct": 9.00,
        },
        recomputed_metrics={
            "sharpeRatio": 1.49,
            "maxDrawdownPct": float("inf"),
        },
    )
    result = engine.check_metric_consistency(evidence=evidence, policy=_policy(tolerance_pct=1.0))
    assert result.status == "fail"
    assert "metric_non_numeric:maxDrawdownPct" in result.mismatches
    assert "metric_non_numeric:sharpeRatio" in result.mismatches
    assert result.drift_pct > 0.0


def test_metric_consistency_zero_baseline_nonzero_reported_always_fails() -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        reported_metrics={"sharpeRatio": 0.05},
        recomputed_metrics={"sharpeRatio": 0.0},
    )
    result = engine.check_metric_consistency(evidence=evidence, policy=_policy(tolerance_pct=10_000.0))
    assert result.status == "fail"
    assert result.drift_pct > 10_000.0
    assert any(item.startswith("metric_drift_exceeds_tolerance") for item in result.mismatches)


def test_lineage_completeness_check_passes_when_dataset_refs_and_sources_exist() -> None:
    engine = DeterministicValidationEngine()
    result = engine.check_lineage_completeness(evidence=_base_evidence(), policy=_policy())
    assert result.status == "pass"
    assert result.missing_dataset_ids == ()
    assert result.missing_source_links == ()


def test_lineage_completeness_check_fails_when_source_link_is_missing() -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        lineage={
            "datasets": [
                {
                    "datasetId": "dataset-btc-1h-2025",
                }
            ]
        },
    )
    result = engine.check_lineage_completeness(evidence=evidence, policy=_policy())
    assert result.status == "fail"
    assert result.missing_source_links == ("dataset-btc-1h-2025",)
    assert "lineage_source_missing:dataset-btc-1h-2025" in result.violations


def test_lineage_completeness_normalizes_requested_dataset_ids() -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        dataset_ids=(" dataset-btc-1h-2025 ",),
        lineage={"datasets": [{"datasetId": "dataset-btc-1h-2025", "sourceRef": "blob://datasets/raw/btc.csv"}]},
    )
    result = engine.check_lineage_completeness(evidence=evidence, policy=_policy())
    assert result.status == "pass"
    assert result.missing_dataset_ids == ()
    assert result.violations == ()


def test_deterministic_failure_blocks_final_decision_and_is_repeatable() -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        rendered_indicators=("ema",),
        chart_payload={"indicators": [{"name": "ema"}]},
        execution_logs=({"orderId": "ord-001", "status": "filled"},),
        lineage=None,
    )
    policy = _policy(tolerance_pct=1.0)

    first = engine.evaluate(evidence=evidence, policy=policy)
    second = engine.evaluate(evidence=evidence, policy=policy)

    assert first == second
    assert first.blocked is True
    assert first.final_decision == "fail"
    assert first.indicator_fidelity.status == "fail"
    assert first.trade_coherence.status == "fail"
    assert first.lineage_completeness.status == "fail"
    assert "missing_indicator_hard_fail" in first.block_reasons
    assert "trade_coherence_failed" in first.block_reasons
    assert "lineage_incomplete" in first.block_reasons


def test_policy_tolerance_changes_metric_outcome_without_changing_evidence() -> None:
    engine = DeterministicValidationEngine()
    evidence = _base_evidence()
    loose = _policy(tolerance_pct=1.0)
    strict = _policy(tolerance_pct=0.5)

    loose_result = engine.evaluate(evidence=evidence, policy=loose)
    strict_result = engine.evaluate(evidence=evidence, policy=strict)

    assert loose_result.metric_consistency.status == "pass"
    assert loose_result.final_decision == "pass"
    assert strict_result.metric_consistency.status == "fail"
    assert strict_result.final_decision == "fail"


def test_canonical_artifact_contains_deterministic_output_and_blocks_on_fail() -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        lineage={"datasets": [{"datasetId": "dataset-btc-1h-2025"}]},
    )
    result = engine.evaluate(evidence=evidence, policy=_policy(tolerance_pct=1.0))
    context = ValidationArtifactContext(
        run_id="valrun-20260217-0001",
        request_id="req-validation-run-001",
        tenant_id="tenant-001",
        user_id="user-001",
        strategy_id="strat-001",
        provider_ref_id="lona-strategy-123",
        prompt="Build zig-zag strategy for BTC 1h with trend filter",
        requested_indicators=("zigzag", "ema"),
        dataset_ids=("dataset-btc-1h-2025",),
        backtest_report_ref="blob://validation/valrun-20260217-0001/backtest-report.json",
        strategy_code_ref="blob://validation/valrun-20260217-0001/strategy.py",
        trades_ref="blob://validation/valrun-20260217-0001/trades.json",
        execution_logs_ref="blob://validation/valrun-20260217-0001/execution.log",
        chart_payload_ref="blob://validation/valrun-20260217-0001/chart-payload.json",
    )

    artifact = engine.build_canonical_artifact(
        context=context,
        result=result,
        policy=_policy(tolerance_pct=1.0),
        created_at="2026-02-17T10:30:00Z",
    )

    assert artifact["finalDecision"] == "fail"
    checks = artifact["deterministicChecks"]
    assert checks["indicatorFidelity"]["status"] == "pass"
    assert checks["tradeCoherence"]["status"] == "fail"
    assert checks["metricConsistency"]["status"] == "pass"
    assert any(item.startswith("lineage:") for item in checks["tradeCoherence"]["violations"])
    assert any(
        finding.check == "trade_coherence" and finding.code == "lineage"
        for finding in result.findings
    )
    assert not any(
        finding.check == "lineage_completeness" and finding.code == "lineage_source_missing"
        for finding in result.findings
    )

    schema = _load_schema(VALIDATION_RUN_SCHEMA_PATH)
    _validate_against_schema(artifact, schema)


@pytest.mark.parametrize("profile", ["FAST", "STANDARD", "EXPERT"])
def test_canonical_artifact_uses_agent_review_default_budget_contract(profile: str) -> None:
    engine = DeterministicValidationEngine()
    result = engine.evaluate(evidence=_base_evidence(), policy=ValidationPolicyConfig(profile=profile))
    context = ValidationArtifactContext(
        run_id="valrun-20260217-0002",
        request_id="req-validation-run-002",
        tenant_id="tenant-001",
        user_id="user-001",
        strategy_id="strat-001",
        provider_ref_id="lona-strategy-123",
        prompt="Build zig-zag strategy for BTC 1h with trend filter",
        requested_indicators=("zigzag", "ema"),
        dataset_ids=("dataset-btc-1h-2025",),
        backtest_report_ref="blob://validation/valrun-20260217-0002/backtest-report.json",
        strategy_code_ref="blob://validation/valrun-20260217-0002/strategy.py",
        trades_ref="blob://validation/valrun-20260217-0002/trades.json",
        execution_logs_ref="blob://validation/valrun-20260217-0002/execution.log",
        chart_payload_ref="blob://validation/valrun-20260217-0002/chart-payload.json",
    )
    artifact = engine.build_canonical_artifact(
        context=context,
        result=result,
        policy=ValidationPolicyConfig(profile=profile),
        created_at="2026-02-17T10:30:00Z",
    )

    expected_limits = ValidationAgentReviewService.DEFAULT_PROFILE_BUDGETS[profile].to_contract_payload()
    assert artifact["agentReview"]["budget"]["limits"] == expected_limits


def test_block_reasons_include_trade_coherence_when_combined_trade_status_fails() -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        lineage={"datasets": [{"datasetId": "dataset-btc-1h-2025"}]},
    )
    result = engine.evaluate(evidence=evidence, policy=_policy(tolerance_pct=1.0))
    assert result.trade_coherence.status == "fail"
    assert "trade_coherence_failed" in result.block_reasons


def test_indicator_collection_uses_fallback_key_when_primary_is_whitespace() -> None:
    engine = DeterministicValidationEngine()
    evidence = replace(
        _base_evidence(),
        requested_indicators=("ema",),
        rendered_indicators=(),
        chart_payload={"indicators": [{"name": "  ", "indicator": "ema"}]},
    )
    result = engine.check_indicator_fidelity(evidence=evidence, policy=_policy())
    assert result.status == "pass"
    assert result.missing_indicators == ()


def test_from_contract_payload_rejects_non_blocking_const_policy_flags() -> None:
    with pytest.raises(ValueError):
        ValidationPolicyConfig.from_contract_payload(
            {
                "profile": "STANDARD",
                "hardFailOnMissingIndicators": False,
                "failClosedOnEvidenceUnavailable": True,
            }
        )

    with pytest.raises(ValueError):
        ValidationPolicyConfig.from_contract_payload(
            {
                "profile": "STANDARD",
                "hardFailOnMissingIndicators": True,
                "failClosedOnEvidenceUnavailable": False,
            }
        )


@pytest.mark.parametrize("invalid_tolerance", [float("nan"), float("inf"), float("-inf")])
def test_resolved_metric_tolerance_rejects_non_finite_values(invalid_tolerance: float) -> None:
    policy = ValidationPolicyConfig(metric_drift_tolerance_pct=invalid_tolerance)
    with pytest.raises(ValueError):
        policy.resolved_metric_tolerance_pct()
