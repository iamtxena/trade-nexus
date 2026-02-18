"""Deterministic validation core for V-02 blocking checks."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Literal

from src.platform_api.state_store import utc_now

ValidationCheckStatus = Literal["pass", "fail"]
ValidationDecision = Literal["pass", "fail"]
ValidationProfile = Literal["FAST", "STANDARD", "EXPERT"]

_PROFILE_METRIC_TOLERANCE_PCT: dict[ValidationProfile, float] = {
    "FAST": 0.5,
    "STANDARD": 1.0,
    "EXPERT": 0.25,
}

_LIFECYCLE_ALIASES: dict[str, str] = {
    "created": "created",
    "submitted": "created",
    "submit": "created",
    "open": "accepted",
    "accepted": "accepted",
    "acknowledged": "accepted",
    "partially_filled": "partially_filled",
    "partial_fill": "partially_filled",
    "partialfilled": "partially_filled",
    "filled": "filled",
    "done": "filled",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "rejected": "rejected",
}

_ALLOWED_LIFECYCLE_TRANSITIONS: dict[str, set[str]] = {
    "created": {"accepted", "cancelled", "rejected"},
    "accepted": {"partially_filled", "filled", "cancelled", "rejected"},
    "partially_filled": {"partially_filled", "filled", "cancelled"},
    "filled": set(),
    "cancelled": set(),
    "rejected": set(),
}

_ZERO_BASELINE_DRIFT_SENTINEL_PCT = 1_000_000_000.0


def _as_string(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _first_non_empty_string(*values: object) -> str:
    for value in values:
        text = _as_string(value)
        if text != "":
            return text
    return ""


def _first_non_empty_from_mapping(record: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        text = _as_string(record.get(key))
        if text != "":
            return text
    return ""


def _unique_sorted(values: list[str] | set[str] | tuple[str, ...]) -> tuple[str, ...]:
    normalized = {_as_string(item) for item in values}
    return tuple(sorted(item for item in normalized if item != ""))


def _normalize_indicator(value: str) -> str:
    token = value.strip().lower()
    return "".join(char for char in token if char.isalnum())


def _percent_drift(*, reported: float, recomputed: float) -> float:
    delta = abs(reported - recomputed)
    if recomputed == 0:
        return 0.0 if reported == 0 else _ZERO_BASELINE_DRIFT_SENTINEL_PCT
    return (delta / abs(recomputed)) * 100.0


def _normalize_lifecycle_state(value: object) -> str:
    raw = _as_string(value).lower().replace("-", "_").replace(" ", "_")
    if raw == "":
        return ""
    if raw in _LIFECYCLE_ALIASES:
        return _LIFECYCLE_ALIASES[raw]
    tokens = tuple(token for token in raw.split("_") if token != "")
    if not tokens:
        return ""
    if any(token.startswith("pending") for token in tokens):
        return ""
    if any(token in {"not", "no", "never", "un", "non"} for token in tokens):
        return ""

    def _has_any(*allowed: str) -> bool:
        return any(token in allowed for token in tokens)

    def _has_prefix(prefix: str) -> bool:
        return any(token.startswith(prefix) for token in tokens)

    if (_has_any("partial", "partially") or _has_prefix("partial")) and (
        _has_any("fill", "filled") or _has_prefix("fill")
    ):
        return "partially_filled"
    if _has_any("fill", "filled") or _has_prefix("fill"):
        return "filled"
    if _has_any("cancel", "cancelled", "canceled") or _has_prefix("cancel"):
        return "cancelled"
    if _has_any("reject", "rejected") or _has_prefix("reject"):
        return "rejected"
    if _has_any("accept", "accepted", "open", "ack", "acknowledged") or _has_prefix("ack"):
        return "accepted"
    if _has_any("create", "created", "submit", "submitted", "place", "placed") or _has_prefix("create"):
        return "created"
    return ""


def _extract_order_id(record: dict[str, Any]) -> str:
    for key in ("orderId", "order_id", "providerOrderId", "provider_order_id"):
        candidate = _as_string(record.get(key))
        if candidate != "":
            return candidate
    return ""


def _extract_lineage_dataset_id(record: dict[str, Any]) -> str:
    for key in ("datasetId", "dataset_id", "id"):
        candidate = _as_string(record.get(key))
        if candidate != "":
            return candidate
    return ""


def _extract_lineage_source_ref(record: dict[str, Any]) -> str:
    for key in ("sourceRef", "source_ref", "source", "sourceDatasetId", "source_id", "ref"):
        candidate = _as_string(record.get(key))
        if candidate != "":
            return candidate
    return ""


@dataclass(frozen=True)
class ValidationPolicyConfig:
    profile: ValidationProfile = "STANDARD"
    block_merge_on_fail: bool = True
    block_release_on_fail: bool = True
    block_merge_on_agent_fail: bool = True
    block_release_on_agent_fail: bool = False
    require_trader_review: bool = False
    hard_fail_on_missing_indicators: bool = True
    fail_closed_on_evidence_unavailable: bool = True
    metric_drift_tolerance_pct: float | None = None

    def resolved_metric_tolerance_pct(self) -> float:
        if self.metric_drift_tolerance_pct is None:
            return _PROFILE_METRIC_TOLERANCE_PCT[self.profile]
        tolerance = float(self.metric_drift_tolerance_pct)
        if not math.isfinite(tolerance):
            raise ValueError("metric_drift_tolerance_pct must be finite.")
        if tolerance < 0:
            raise ValueError("metric_drift_tolerance_pct must be >= 0.")
        return tolerance

    @classmethod
    def from_contract_payload(
        cls,
        payload: dict[str, Any],
        *,
        metric_drift_tolerance_pct: float | None = None,
    ) -> ValidationPolicyConfig:
        profile = payload.get("profile", "STANDARD")
        if profile not in _PROFILE_METRIC_TOLERANCE_PCT:
            raise ValueError(f"Unsupported validation profile: {profile!r}")
        hard_fail_on_missing = payload.get("hardFailOnMissingIndicators", True)
        if hard_fail_on_missing is not True:
            raise ValueError("hardFailOnMissingIndicators must be true.")
        fail_closed_on_missing_evidence = payload.get("failClosedOnEvidenceUnavailable", True)
        if fail_closed_on_missing_evidence is not True:
            raise ValueError("failClosedOnEvidenceUnavailable must be true.")
        return cls(
            profile=profile,
            block_merge_on_fail=bool(payload.get("blockMergeOnFail", True)),
            block_release_on_fail=bool(payload.get("blockReleaseOnFail", True)),
            block_merge_on_agent_fail=bool(payload.get("blockMergeOnAgentFail", True)),
            block_release_on_agent_fail=bool(payload.get("blockReleaseOnAgentFail", False)),
            require_trader_review=bool(payload.get("requireTraderReview", False)),
            hard_fail_on_missing_indicators=True,
            fail_closed_on_evidence_unavailable=True,
            metric_drift_tolerance_pct=metric_drift_tolerance_pct,
        )

    def to_contract_payload(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "blockMergeOnFail": self.block_merge_on_fail,
            "blockReleaseOnFail": self.block_release_on_fail,
            "blockMergeOnAgentFail": self.block_merge_on_agent_fail,
            "blockReleaseOnAgentFail": self.block_release_on_agent_fail,
            "requireTraderReview": self.require_trader_review,
            "hardFailOnMissingIndicators": self.hard_fail_on_missing_indicators,
            "failClosedOnEvidenceUnavailable": self.fail_closed_on_evidence_unavailable,
        }


@dataclass(frozen=True)
class DeterministicValidationEvidence:
    requested_indicators: tuple[str, ...] = ()
    rendered_indicators: tuple[str, ...] = ()
    chart_payload: dict[str, Any] | None = None
    trades: tuple[dict[str, Any], ...] = ()
    execution_logs: tuple[dict[str, Any], ...] = ()
    reported_metrics: dict[str, float] = field(default_factory=dict)
    recomputed_metrics: dict[str, float] = field(default_factory=dict)
    dataset_ids: tuple[str, ...] = ()
    lineage: dict[str, Any] | None = None


@dataclass(frozen=True)
class ValidationFinding:
    code: str
    check: str
    message: str
    severity: Literal["error", "warning"] = "error"


@dataclass(frozen=True)
class IndicatorFidelityCheckResult:
    status: ValidationCheckStatus
    missing_indicators: tuple[str, ...]


@dataclass(frozen=True)
class TradeCoherenceCheckResult:
    status: ValidationCheckStatus
    violations: tuple[str, ...]


@dataclass(frozen=True)
class MetricConsistencyCheckResult:
    status: ValidationCheckStatus
    drift_pct: float
    tolerance_pct: float
    mismatches: tuple[str, ...]


@dataclass(frozen=True)
class LineageCompletenessCheckResult:
    status: ValidationCheckStatus
    missing_dataset_ids: tuple[str, ...]
    missing_source_links: tuple[str, ...]
    violations: tuple[str, ...]


@dataclass(frozen=True)
class DeterministicValidationResult:
    status: ValidationDecision
    final_decision: ValidationDecision
    blocked: bool
    block_reasons: tuple[str, ...]
    indicator_fidelity: IndicatorFidelityCheckResult
    trade_coherence: TradeCoherenceCheckResult
    metric_consistency: MetricConsistencyCheckResult
    lineage_completeness: LineageCompletenessCheckResult
    findings: tuple[ValidationFinding, ...]

    def to_contract_deterministic_checks(self) -> dict[str, Any]:
        return {
            "indicatorFidelity": {
                "status": self.indicator_fidelity.status,
                "missingIndicators": list(self.indicator_fidelity.missing_indicators),
            },
            "tradeCoherence": {
                "status": self.trade_coherence.status,
                "violations": list(self.trade_coherence.violations),
            },
            "metricConsistency": {
                "status": self.metric_consistency.status,
                "driftPct": round(self.metric_consistency.drift_pct, 6),
            },
        }


@dataclass(frozen=True)
class ValidationArtifactContext:
    run_id: str
    request_id: str
    tenant_id: str
    user_id: str
    strategy_id: str
    provider_ref_id: str
    prompt: str
    requested_indicators: tuple[str, ...]
    dataset_ids: tuple[str, ...]
    backtest_report_ref: str
    strategy_code_ref: str
    trades_ref: str
    execution_logs_ref: str
    chart_payload_ref: str


class DeterministicValidationEngine:
    """Evaluates deterministic validation checks and emits canonical artifacts."""

    def evaluate(
        self,
        *,
        evidence: DeterministicValidationEvidence,
        policy: ValidationPolicyConfig,
    ) -> DeterministicValidationResult:
        indicator_result = self.check_indicator_fidelity(evidence=evidence, policy=policy)
        trade_result = self.check_trade_coherence(evidence=evidence, policy=policy)
        metric_result = self.check_metric_consistency(evidence=evidence, policy=policy)
        lineage_result = self.check_lineage_completeness(evidence=evidence, policy=policy)

        lineage_violations_in_trade = tuple(f"lineage:{item}" for item in lineage_result.violations)
        combined_trade_violations = _unique_sorted(
            tuple((*trade_result.violations, *lineage_violations_in_trade))
        )
        combined_trade_result = TradeCoherenceCheckResult(
            status="fail" if combined_trade_violations else "pass",
            violations=combined_trade_violations,
        )

        block_reasons: list[str] = []
        if indicator_result.status == "fail":
            block_reasons.append("missing_indicator_hard_fail")
        if combined_trade_result.status == "fail":
            block_reasons.append("trade_coherence_failed")
        if metric_result.status == "fail":
            block_reasons.append("metric_consistency_failed")
        if lineage_result.status == "fail":
            block_reasons.append("lineage_incomplete")

        final_decision: ValidationDecision = "fail" if block_reasons else "pass"
        findings = self._build_findings(
            indicator_result=indicator_result,
            trade_result=combined_trade_result,
            metric_result=metric_result,
            lineage_result=lineage_result,
        )

        return DeterministicValidationResult(
            status=final_decision,
            final_decision=final_decision,
            blocked=final_decision == "fail",
            block_reasons=tuple(block_reasons),
            indicator_fidelity=indicator_result,
            trade_coherence=combined_trade_result,
            metric_consistency=metric_result,
            lineage_completeness=lineage_result,
            findings=findings,
        )

    def check_indicator_fidelity(
        self,
        *,
        evidence: DeterministicValidationEvidence,
        policy: ValidationPolicyConfig,
    ) -> IndicatorFidelityCheckResult:
        requested: dict[str, str] = {}
        for indicator in evidence.requested_indicators:
            name = _as_string(indicator)
            key = _normalize_indicator(name)
            if key != "" and key not in requested:
                requested[key] = name

        rendered_keys = {
            _normalize_indicator(indicator)
            for indicator in self._collect_rendered_indicators(evidence=evidence)
            if _normalize_indicator(indicator) != ""
        }
        missing = tuple(sorted(name for key, name in requested.items() if key not in rendered_keys))

        if missing and policy.hard_fail_on_missing_indicators:
            return IndicatorFidelityCheckResult(status="fail", missing_indicators=missing)
        return IndicatorFidelityCheckResult(status="pass", missing_indicators=missing)

    def check_trade_coherence(
        self,
        *,
        evidence: DeterministicValidationEvidence,
        policy: ValidationPolicyConfig,
    ) -> TradeCoherenceCheckResult:
        violations: list[str] = []
        log_states_by_order: dict[str, list[str]] = defaultdict(list)

        for entry in evidence.execution_logs:
            order_id = _extract_order_id(entry)
            state = _normalize_lifecycle_state(
                _first_non_empty_string(
                    entry.get("status"),
                    entry.get("state"),
                    entry.get("event"),
                )
            )
            if order_id == "":
                violations.append("execution_log_missing_order_id")
                continue
            if state == "":
                violations.append(f"execution_log_unknown_state:{order_id}")
                continue
            log_states_by_order[order_id].append(state)

        if not evidence.trades and not evidence.execution_logs:
            if policy.fail_closed_on_evidence_unavailable:
                violations.append("trade_evidence_unavailable")
            return TradeCoherenceCheckResult(
                status="fail" if violations else "pass",
                violations=_unique_sorted(tuple(violations)),
            )

        for order_id in sorted(log_states_by_order):
            states = log_states_by_order[order_id]
            if not states:
                continue
            if states[0] != "created":
                violations.append(f"invalid_lifecycle_start:{order_id}:{states[0]}")
            previous = states[0]
            for current in states[1:]:
                allowed = _ALLOWED_LIFECYCLE_TRANSITIONS.get(previous, set())
                if current not in allowed:
                    violations.append(f"invalid_lifecycle_transition:{order_id}:{previous}->{current}")
                previous = current

        trade_order_ids: set[str] = set()
        for trade in evidence.trades:
            order_id = _extract_order_id(trade)
            if order_id == "":
                violations.append("trade_missing_order_id")
                continue
            trade_order_ids.add(order_id)
            states = log_states_by_order.get(order_id)
            if not states:
                violations.append(f"trade_without_execution_log:{order_id}")
                continue
            if "filled" not in states:
                violations.append(f"trade_without_fill_event:{order_id}")

        filled_order_ids = {order_id for order_id, states in log_states_by_order.items() if "filled" in states}
        for order_id in sorted(filled_order_ids - trade_order_ids):
            violations.append(f"fill_without_trade:{order_id}")

        if policy.fail_closed_on_evidence_unavailable and evidence.trades and not evidence.execution_logs:
            violations.append("execution_evidence_unavailable")

        normalized = _unique_sorted(tuple(violations))
        return TradeCoherenceCheckResult(
            status="fail" if normalized else "pass",
            violations=normalized,
        )

    def check_metric_consistency(
        self,
        *,
        evidence: DeterministicValidationEvidence,
        policy: ValidationPolicyConfig,
    ) -> MetricConsistencyCheckResult:
        tolerance_pct = policy.resolved_metric_tolerance_pct()
        mismatches: list[str] = []
        max_drift = 0.0
        has_structural_mismatch = False

        if not evidence.reported_metrics or not evidence.recomputed_metrics:
            if policy.fail_closed_on_evidence_unavailable:
                return MetricConsistencyCheckResult(
                    status="fail",
                    drift_pct=0.0,
                    tolerance_pct=tolerance_pct,
                    mismatches=("metrics_evidence_unavailable",),
                )
            return MetricConsistencyCheckResult(
                status="pass",
                drift_pct=0.0,
                tolerance_pct=tolerance_pct,
                mismatches=(),
            )

        metric_keys = sorted(set(evidence.reported_metrics) | set(evidence.recomputed_metrics))
        for metric_name in metric_keys:
            if metric_name not in evidence.reported_metrics:
                mismatches.append(f"metric_missing_in_reported:{metric_name}")
                has_structural_mismatch = True
                continue
            if metric_name not in evidence.recomputed_metrics:
                mismatches.append(f"metric_missing_in_recomputed:{metric_name}")
                has_structural_mismatch = True
                continue

            reported_value = evidence.reported_metrics[metric_name]
            recomputed_value = evidence.recomputed_metrics[metric_name]
            if not _is_number(reported_value) or not _is_number(recomputed_value):
                mismatches.append(f"metric_non_numeric:{metric_name}")
                has_structural_mismatch = True
                continue

            drift_pct = _percent_drift(
                reported=float(reported_value),
                recomputed=float(recomputed_value),
            )
            max_drift = max(max_drift, drift_pct)

        if has_structural_mismatch:
            max_drift = max(max_drift, _ZERO_BASELINE_DRIFT_SENTINEL_PCT)

        if max_drift > tolerance_pct:
            mismatches.append(
                "metric_drift_exceeds_tolerance"
                f":max={max_drift:.6f}:tolerance={tolerance_pct:.6f}"
            )

        normalized = _unique_sorted(tuple(mismatches))
        return MetricConsistencyCheckResult(
            status="fail" if normalized else "pass",
            drift_pct=max_drift,
            tolerance_pct=tolerance_pct,
            mismatches=normalized,
        )

    def check_lineage_completeness(
        self,
        *,
        evidence: DeterministicValidationEvidence,
        policy: ValidationPolicyConfig,
    ) -> LineageCompletenessCheckResult:
        violations: list[str] = []
        missing_dataset_ids: list[str] = []
        missing_source_links: list[str] = []

        requested_dataset_ids: set[str] = set()
        for dataset_id in evidence.dataset_ids:
            normalized_dataset_id = _as_string(dataset_id)
            if normalized_dataset_id != "":
                requested_dataset_ids.add(normalized_dataset_id)
        if not requested_dataset_ids and policy.fail_closed_on_evidence_unavailable:
            violations.append("dataset_references_missing")

        lineage = evidence.lineage
        if not isinstance(lineage, dict):
            if policy.fail_closed_on_evidence_unavailable:
                violations.append("lineage_payload_missing")
            return LineageCompletenessCheckResult(
                status="fail" if violations else "pass",
                missing_dataset_ids=(),
                missing_source_links=(),
                violations=_unique_sorted(tuple(violations)),
            )

        lineage_datasets_raw = lineage.get("datasets")
        if not isinstance(lineage_datasets_raw, list) or len(lineage_datasets_raw) == 0:
            if policy.fail_closed_on_evidence_unavailable:
                violations.append("lineage_datasets_missing")
        lineage_dataset_ids: set[str] = set()

        if isinstance(lineage_datasets_raw, list):
            for index, entry in enumerate(lineage_datasets_raw):
                if isinstance(entry, str):
                    dataset_id = _as_string(entry)
                    source_ref = ""
                elif isinstance(entry, dict):
                    dataset_id = _extract_lineage_dataset_id(entry)
                    source_ref = _extract_lineage_source_ref(entry)
                else:
                    violations.append(f"lineage_dataset_entry_invalid:{index}")
                    continue

                if dataset_id == "":
                    violations.append(f"lineage_dataset_id_missing:{index}")
                    continue
                lineage_dataset_ids.add(dataset_id)
                if source_ref == "":
                    missing_source_links.append(dataset_id)

        for dataset_id in sorted(requested_dataset_ids - lineage_dataset_ids):
            missing_dataset_ids.append(dataset_id)
            violations.append(f"lineage_dataset_missing:{dataset_id}")
        for dataset_id in sorted(set(missing_source_links)):
            violations.append(f"lineage_source_missing:{dataset_id}")

        normalized_violations = _unique_sorted(tuple(violations))
        normalized_missing_dataset_ids = _unique_sorted(tuple(missing_dataset_ids))
        normalized_missing_source_links = _unique_sorted(tuple(missing_source_links))
        return LineageCompletenessCheckResult(
            status="fail" if normalized_violations else "pass",
            missing_dataset_ids=normalized_missing_dataset_ids,
            missing_source_links=normalized_missing_source_links,
            violations=normalized_violations,
        )

    def build_canonical_artifact(
        self,
        *,
        context: ValidationArtifactContext,
        result: DeterministicValidationResult,
        policy: ValidationPolicyConfig,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        created_timestamp = created_at or utc_now()
        trader_status = "requested" if policy.require_trader_review else "not_requested"

        return {
            "schemaVersion": "validation-run.v1",
            "runId": context.run_id,
            "createdAt": created_timestamp,
            "requestId": context.request_id,
            "tenantId": context.tenant_id,
            "userId": context.user_id,
            "strategyRef": {
                "strategyId": context.strategy_id,
                "provider": "lona",
                "providerRefId": context.provider_ref_id,
            },
            "inputs": {
                "prompt": context.prompt,
                "requestedIndicators": list(context.requested_indicators),
                "datasetIds": list(context.dataset_ids),
                "backtestReportRef": context.backtest_report_ref,
            },
            "outputs": {
                "strategyCodeRef": context.strategy_code_ref,
                "backtestReportRef": context.backtest_report_ref,
                "tradesRef": context.trades_ref,
                "executionLogsRef": context.execution_logs_ref,
                "chartPayloadRef": context.chart_payload_ref,
            },
            "deterministicChecks": result.to_contract_deterministic_checks(),
            "agentReview": {
                "status": "pass",
                "summary": "Agent lane not executed in deterministic-only validation run.",
                "findings": [],
            },
            "traderReview": {
                "required": policy.require_trader_review,
                "status": trader_status,
                "comments": [],
            },
            "policy": policy.to_contract_payload(),
            "finalDecision": result.final_decision,
        }

    def _collect_rendered_indicators(self, *, evidence: DeterministicValidationEvidence) -> tuple[str, ...]:
        rendered: list[str] = [item for item in evidence.rendered_indicators if _as_string(item) != ""]
        payload = evidence.chart_payload
        if not isinstance(payload, dict):
            return tuple(rendered)

        direct = payload.get("indicators")
        if isinstance(direct, list):
            for item in direct:
                if isinstance(item, str):
                    rendered.append(item)
                    continue
                if isinstance(item, dict):
                    name = _first_non_empty_from_mapping(item, ("name", "indicator", "id"))
                    if name != "":
                        rendered.append(name)

        panes = payload.get("panes")
        if isinstance(panes, list):
            for pane in panes:
                if not isinstance(pane, dict):
                    continue
                pane_indicators = pane.get("indicators")
                if not isinstance(pane_indicators, list):
                    continue
                for item in pane_indicators:
                    if isinstance(item, str):
                        rendered.append(item)
                    elif isinstance(item, dict):
                        name = _first_non_empty_from_mapping(item, ("name", "indicator", "id"))
                        if name != "":
                            rendered.append(name)
        return tuple(rendered)

    def _build_findings(
        self,
        *,
        indicator_result: IndicatorFidelityCheckResult,
        trade_result: TradeCoherenceCheckResult,
        metric_result: MetricConsistencyCheckResult,
        lineage_result: LineageCompletenessCheckResult,
    ) -> tuple[ValidationFinding, ...]:
        findings: list[ValidationFinding] = []
        lineage_from_trade: set[str] = set()
        for indicator in indicator_result.missing_indicators:
            findings.append(
                ValidationFinding(
                    code="missing_indicator",
                    check="indicator_fidelity",
                    message=f"Requested indicator {indicator!r} is missing from rendered evidence.",
                )
            )
        for violation in trade_result.violations:
            code, _, detail = violation.partition(":")
            if code == "lineage" and detail != "":
                lineage_from_trade.add(detail)
            findings.append(
                ValidationFinding(
                    code=code,
                    check="trade_coherence",
                    message=detail if detail else violation,
                )
            )
        for mismatch in metric_result.mismatches:
            code, _, detail = mismatch.partition(":")
            findings.append(
                ValidationFinding(
                    code=code,
                    check="metric_consistency",
                    message=detail if detail else mismatch,
                )
            )
        for violation in lineage_result.violations:
            if violation in lineage_from_trade:
                continue
            code, _, detail = violation.partition(":")
            findings.append(
                ValidationFinding(
                    code=code,
                    check="lineage_completeness",
                    message=detail if detail else violation,
                )
            )
        return tuple(findings)
