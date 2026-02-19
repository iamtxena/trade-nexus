"""Contract tests for V-03 bounded agent review lane (#227)."""

from __future__ import annotations

from typing import Any

import pytest

from src.platform_api.services.validation_agent_review_service import (
    AgentReviewBudget,
    AgentReviewFinding,
    AgentReviewToolCall,
    ValidationAgentReviewService,
    ValidationProfile,
)
from tests.contracts.test_validation_schema_contract import (
    VALIDATION_AGENT_REVIEW_RESULT_SCHEMA_PATH,
    _load_schema,
    _validate_against_schema,
)


class _RecordingToolExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def run(self, *, tool_name: str, evidence_ref: str) -> object:
        self.calls.append((tool_name, evidence_ref))
        return {"status": "ok"}


class _FailingToolExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def run(self, *, tool_name: str, evidence_ref: str) -> object:
        self.calls.append((tool_name, evidence_ref))
        raise RuntimeError("simulated tool executor failure")


class _OutOfScopeFindingService(ValidationAgentReviewService):
    def _tool_payload_findings(self, *, evidence_ref: str, payload: object) -> list[AgentReviewFinding]:
        _ = payload
        return [
            AgentReviewFinding(
                id="agent-traceability-out-of-scope",
                priority=2,
                confidence=0.7,
                summary="Synthetic out-of-scope finding for contract guardrail test.",
                evidence_refs=("blob://outside/ref",),
            )
        ]


class _DuplicateRefFindingService(ValidationAgentReviewService):
    def _tool_payload_findings(self, *, evidence_ref: str, payload: object) -> list[AgentReviewFinding]:
        _ = payload
        return [
            AgentReviewFinding(
                id="agent-traceability-duplicate-refs",
                priority=2,
                confidence=0.75,
                summary="Synthetic duplicate-ref finding for normalization test.",
                evidence_refs=(evidence_ref, evidence_ref),
            )
        ]


class _SequenceClock:
    def __init__(self, *values: float) -> None:
        self._values = values
        self._index = 0

    def __call__(self) -> float:
        if len(self._values) == 0:
            return 0.0
        if self._index >= len(self._values):
            return self._values[-1]
        value = self._values[self._index]
        self._index += 1
        return value


def _policy(profile: str) -> dict[str, Any]:
    return {
        "profile": profile,
        "blockMergeOnFail": True,
        "blockReleaseOnFail": True,
        "blockMergeOnAgentFail": profile != "FAST",
        "blockReleaseOnAgentFail": profile == "EXPERT",
        "requireTraderReview": profile == "EXPERT",
        "hardFailOnMissingIndicators": True,
        "failClosedOnEvidenceUnavailable": True,
    }


def _snapshot(*, profile: str = "STANDARD") -> dict[str, Any]:
    return {
        "schemaVersion": "validation-llm-snapshot.v1",
        "runId": "valrun-20260217-0001",
        "sourceSchemaVersion": "validation-run.v1",
        "generatedAt": "2026-02-17T10:31:00Z",
        "strategyId": "strat-001",
        "requestedIndicators": ["zigzag", "ema"],
        "deterministicChecks": {
            "indicatorFidelityStatus": "pass",
            "tradeCoherenceStatus": "pass",
            "metricConsistencyStatus": "pass",
        },
        "policy": _policy(profile),
        "evidenceRefs": [
            {"kind": "strategy_code", "ref": "blob://validation/valrun-20260217-0001/strategy.py"},
            {"kind": "backtest_report", "ref": "blob://validation/valrun-20260217-0001/backtest-report.json"},
            {"kind": "trades", "ref": "blob://validation/valrun-20260217-0001/trades.json"},
            {"kind": "execution_logs", "ref": "blob://validation/valrun-20260217-0001/execution.log"},
            {"kind": "chart_payload", "ref": "blob://validation/valrun-20260217-0001/chart-payload.json"},
        ],
        "finalDecision": "pass",
    }


def _budgets(
    *,
    fast: AgentReviewBudget | None = None,
    standard: AgentReviewBudget | None = None,
    expert: AgentReviewBudget | None = None,
) -> dict[ValidationProfile, AgentReviewBudget]:
    return {
        "FAST": fast or AgentReviewBudget(1.0, 2000, 2, 5),
        "STANDARD": standard or AgentReviewBudget(1.0, 2000, 2, 5),
        "EXPERT": expert or AgentReviewBudget(1.0, 2000, 2, 5),
    }


def test_review_output_contract_shape_is_machine_readable() -> None:
    service = ValidationAgentReviewService()
    snapshot = _snapshot(profile="STANDARD")
    snapshot["deterministicChecks"]["indicatorFidelityStatus"] = "fail"

    payload = service.review(snapshot=snapshot, tool_calls=()).to_contract_payload()

    assert set(payload) == {"status", "summary", "findings", "budget"}
    assert payload["status"] in {"pass", "conditional_pass", "fail"}
    assert isinstance(payload["summary"], str) and payload["summary"]
    assert isinstance(payload["findings"], list) and len(payload["findings"]) >= 1

    finding = payload["findings"][0]
    assert set(finding) == {"id", "priority", "confidence", "summary", "evidenceRefs"}
    assert isinstance(finding["id"], str) and finding["id"]
    assert isinstance(finding["priority"], int) and 0 <= finding["priority"] <= 3
    assert isinstance(finding["confidence"], (int, float)) and 0 <= finding["confidence"] <= 1
    assert isinstance(finding["summary"], str) and finding["summary"]
    assert isinstance(finding["evidenceRefs"], list) and len(finding["evidenceRefs"]) >= 1
    assert all(isinstance(ref, str) and ref for ref in finding["evidenceRefs"])

    budget = payload["budget"]
    assert set(budget) == {"profile", "limits", "usage", "withinBudget", "breachReason"}
    assert budget["profile"] in {"FAST", "STANDARD", "EXPERT"}
    assert set(budget["limits"]) == {"maxRuntimeSeconds", "maxTokens", "maxToolCalls", "maxFindings"}
    assert set(budget["usage"]) == {"runtimeSeconds", "tokensUsed", "toolCallsUsed"}
    assert isinstance(budget["withinBudget"], bool)


def test_review_output_contract_validates_against_agent_review_schema() -> None:
    service = ValidationAgentReviewService()
    snapshot = _snapshot(profile="STANDARD")
    snapshot["deterministicChecks"]["tradeCoherenceStatus"] = "fail"

    payload = service.review(snapshot=snapshot, tool_calls=()).to_contract_payload()
    schema = _load_schema(VALIDATION_AGENT_REVIEW_RESULT_SCHEMA_PATH)
    _validate_against_schema(payload, schema)


def test_trade_coherence_deterministic_finding_uses_trade_and_execution_log_refs() -> None:
    service = ValidationAgentReviewService()
    snapshot = _snapshot(profile="STANDARD")
    snapshot["deterministicChecks"]["tradeCoherenceStatus"] = "fail"

    result = service.review(snapshot=snapshot, tool_calls=())
    finding = next(item for item in result.findings if item.id == "agent-check-tradecoherencestatus")
    refs = set(finding.evidence_refs)
    assert "blob://validation/valrun-20260217-0001/trades.json" in refs
    assert "blob://validation/valrun-20260217-0001/execution.log" in refs


@pytest.mark.parametrize("profile", ["FAST", "STANDARD", "EXPERT"])
def test_profile_budget_selection_uses_snapshot_profile(profile: str) -> None:
    custom_budgets = _budgets(
        fast=AgentReviewBudget(2.0, 3000, 1, 3),
        standard=AgentReviewBudget(3.0, 4000, 2, 4),
        expert=AgentReviewBudget(4.0, 5000, 3, 5),
    )
    service = ValidationAgentReviewService(profile_budgets=custom_budgets)
    result = service.review(snapshot=_snapshot(profile=profile), tool_calls=())

    assert result.budget.profile == profile
    assert result.budget.limits == custom_budgets[profile]
    assert result.budget.within_budget is True


def test_review_fails_closed_when_token_budget_is_exceeded() -> None:
    custom_budgets = _budgets(standard=AgentReviewBudget(1.0, 1, 2, 5))
    service = ValidationAgentReviewService(profile_budgets=custom_budgets)

    result = service.review(snapshot=_snapshot(profile="STANDARD"), tool_calls=())

    assert result.status == "fail"
    assert result.budget.within_budget is False
    assert result.budget.breach_reason == "token_budget_exceeded"


def test_review_fails_closed_when_tool_budget_is_exceeded() -> None:
    custom_budgets = _budgets(fast=AgentReviewBudget(1.0, 5000, 0, 5))
    service = ValidationAgentReviewService(profile_budgets=custom_budgets)
    snapshot = _snapshot(profile="FAST")
    first_ref = snapshot["evidenceRefs"][0]["ref"]

    result = service.review(
        snapshot=snapshot,
        tool_calls=(AgentReviewToolCall(tool_name="fetch_evidence_ref", evidence_ref=first_ref),),
    )

    assert result.status == "fail"
    assert result.budget.within_budget is False
    assert result.budget.breach_reason == "tool_budget_exceeded"


def test_review_fails_closed_when_runtime_budget_is_exceeded() -> None:
    custom_budgets = _budgets(fast=AgentReviewBudget(0.2, 5000, 2, 5))
    clock = _SequenceClock(0.0, 1.0, 1.0)
    service = ValidationAgentReviewService(profile_budgets=custom_budgets, clock=clock)

    result = service.review(snapshot=_snapshot(profile="FAST"), tool_calls=())

    assert result.status == "fail"
    assert result.budget.within_budget is False
    assert result.budget.breach_reason == "runtime_budget_exceeded"


def test_review_blocks_non_allowlisted_tool_calls() -> None:
    executor = _RecordingToolExecutor()
    custom_budgets = _budgets(fast=AgentReviewBudget(1.0, 5000, 2, 5))
    service = ValidationAgentReviewService(tool_executor=executor, profile_budgets=custom_budgets)
    snapshot = _snapshot(profile="FAST")
    first_ref = snapshot["evidenceRefs"][0]["ref"]

    result = service.review(
        snapshot=snapshot,
        tool_calls=(AgentReviewToolCall(tool_name="shell_exec", evidence_ref=first_ref),),
    )

    assert result.status == "fail"
    assert result.budget.within_budget is False
    assert result.budget.breach_reason == "tool_not_allowed"
    assert executor.calls == []


def test_review_blocks_tool_calls_for_out_of_scope_evidence_refs() -> None:
    executor = _RecordingToolExecutor()
    custom_budgets = _budgets(fast=AgentReviewBudget(1.0, 5000, 2, 5))
    service = ValidationAgentReviewService(tool_executor=executor, profile_budgets=custom_budgets)

    result = service.review(
        snapshot=_snapshot(profile="FAST"),
        tool_calls=(AgentReviewToolCall(tool_name="fetch_evidence_ref", evidence_ref="blob://outside/ref"),),
    )

    assert result.status == "fail"
    assert result.budget.within_budget is False
    assert result.budget.breach_reason == "tool_ref_out_of_scope"
    assert executor.calls == []


def test_review_fails_closed_when_tool_executor_raises_exception() -> None:
    executor = _FailingToolExecutor()
    custom_budgets = _budgets(fast=AgentReviewBudget(1.0, 5000, 2, 5))
    service = ValidationAgentReviewService(tool_executor=executor, profile_budgets=custom_budgets)
    snapshot = _snapshot(profile="FAST")
    first_ref = snapshot["evidenceRefs"][0]["ref"]

    result = service.review(
        snapshot=snapshot,
        tool_calls=(AgentReviewToolCall(tool_name="fetch_evidence_ref", evidence_ref=first_ref),),
    )

    assert result.status == "fail"
    assert result.budget.within_budget is False
    assert result.budget.breach_reason == "tool_executor_error:RuntimeError"
    assert result.budget.usage.tool_calls_used == 1
    assert executor.calls == [("fetch_evidence_ref", first_ref)]


def test_review_fails_closed_when_finding_references_out_of_scope_evidence() -> None:
    custom_budgets = _budgets(fast=AgentReviewBudget(1.0, 5000, 2, 5))
    service = _OutOfScopeFindingService(profile_budgets=custom_budgets)
    snapshot = _snapshot(profile="FAST")
    first_ref = snapshot["evidenceRefs"][0]["ref"]

    result = service.review(
        snapshot=snapshot,
        tool_calls=(AgentReviewToolCall(tool_name="fetch_evidence_ref", evidence_ref=first_ref),),
    )

    assert result.status == "fail"
    assert result.budget.within_budget is False
    assert result.budget.breach_reason == "finding_ref_out_of_scope"


def test_review_normalizes_duplicate_finding_evidence_refs() -> None:
    custom_budgets = _budgets(fast=AgentReviewBudget(1.0, 5000, 2, 5))
    service = _DuplicateRefFindingService(profile_budgets=custom_budgets)
    snapshot = _snapshot(profile="FAST")
    first_ref = snapshot["evidenceRefs"][0]["ref"]

    result = service.review(
        snapshot=snapshot,
        tool_calls=(AgentReviewToolCall(tool_name="fetch_evidence_ref", evidence_ref=first_ref),),
    )

    finding = next(item for item in result.findings if item.id == "agent-traceability-duplicate-refs")
    assert finding.evidence_refs == (first_ref,)
