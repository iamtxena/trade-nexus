"""Bounded-cost agent review lane for validation compact snapshots (V-03 / #227)."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha1
from typing import Any, Literal, Protocol, cast

ValidationDecision = Literal["pass", "conditional_pass", "fail"]
ValidationProfile = Literal["FAST", "STANDARD", "EXPERT"]

_ALLOWED_TOOL_NAME = "fetch_evidence_ref"
_ALLOWED_TOOLS: frozenset[str] = frozenset({_ALLOWED_TOOL_NAME})
_PROFILE_ORDER: tuple[ValidationProfile, ...] = ("FAST", "STANDARD", "EXPERT")


def _estimate_tokens(value: object) -> int:
    """Estimate token count conservatively from serialized payload size."""
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return max(1, math.ceil(len(serialized) / 4))


def _stable_suffix(value: str) -> str:
    digest = sha1(value.encode("utf-8")).hexdigest()
    return digest[:10]


@dataclass(frozen=True)
class AgentReviewBudget:
    max_runtime_seconds: float
    max_tokens: int
    max_tool_calls: int
    max_findings: int

    def __post_init__(self) -> None:
        if not math.isfinite(self.max_runtime_seconds) or self.max_runtime_seconds <= 0:
            raise ValueError("max_runtime_seconds must be finite and > 0.")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be > 0.")
        if self.max_tool_calls < 0:
            raise ValueError("max_tool_calls must be >= 0.")
        if self.max_findings <= 0:
            raise ValueError("max_findings must be > 0.")

    def to_contract_payload(self) -> dict[str, Any]:
        return {
            "maxRuntimeSeconds": self.max_runtime_seconds,
            "maxTokens": self.max_tokens,
            "maxToolCalls": self.max_tool_calls,
            "maxFindings": self.max_findings,
        }


@dataclass(frozen=True)
class AgentReviewBudgetUsage:
    runtime_seconds: float
    tokens_used: int
    tool_calls_used: int

    def __post_init__(self) -> None:
        if not math.isfinite(self.runtime_seconds) or self.runtime_seconds < 0:
            raise ValueError("runtime_seconds must be finite and >= 0.")
        if self.tokens_used < 0:
            raise ValueError("tokens_used must be >= 0.")
        if self.tool_calls_used < 0:
            raise ValueError("tool_calls_used must be >= 0.")

    def to_contract_payload(self) -> dict[str, Any]:
        return {
            "runtimeSeconds": self.runtime_seconds,
            "tokensUsed": self.tokens_used,
            "toolCallsUsed": self.tool_calls_used,
        }


@dataclass(frozen=True)
class AgentReviewBudgetReport:
    profile: ValidationProfile
    limits: AgentReviewBudget
    usage: AgentReviewBudgetUsage
    within_budget: bool
    breach_reason: str | None = None

    def __post_init__(self) -> None:
        if self.within_budget and self.breach_reason is not None:
            raise ValueError("breach_reason must be None when within_budget is True.")
        if not self.within_budget and (self.breach_reason is None or self.breach_reason.strip() == ""):
            raise ValueError("breach_reason is required when within_budget is False.")

    def to_contract_payload(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "limits": self.limits.to_contract_payload(),
            "usage": self.usage.to_contract_payload(),
            "withinBudget": self.within_budget,
            "breachReason": self.breach_reason,
        }


@dataclass(frozen=True)
class AgentReviewFinding:
    id: str
    priority: int
    confidence: float
    summary: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.id.strip() == "":
            raise ValueError("id must be non-empty.")
        if self.priority < 0 or self.priority > 3:
            raise ValueError("priority must be between 0 and 3.")
        if not math.isfinite(self.confidence) or self.confidence < 0 or self.confidence > 1:
            raise ValueError("confidence must be finite and between 0 and 1.")
        if self.summary.strip() == "":
            raise ValueError("summary must be non-empty.")
        if len(self.evidence_refs) == 0:
            raise ValueError("evidence_refs must have at least one entry.")
        for ref in self.evidence_refs:
            if ref.strip() == "":
                raise ValueError("evidence_refs entries must be non-empty.")

    def to_contract_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "priority": self.priority,
            "confidence": self.confidence,
            "summary": self.summary,
            "evidenceRefs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class AgentReviewResult:
    status: ValidationDecision
    summary: str
    findings: tuple[AgentReviewFinding, ...]
    budget: AgentReviewBudgetReport

    def to_contract_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "findings": [finding.to_contract_payload() for finding in self.findings],
            "budget": self.budget.to_contract_payload(),
        }


@dataclass(frozen=True)
class AgentReviewToolCall:
    tool_name: str
    evidence_ref: str

    def __post_init__(self) -> None:
        if self.tool_name.strip() == "":
            raise ValueError("tool_name must be non-empty.")
        if self.evidence_ref.strip() == "":
            raise ValueError("evidence_ref must be non-empty.")


@dataclass(frozen=True)
class _SnapshotEvidenceRef:
    kind: str
    ref: str


@dataclass(frozen=True)
class _SnapshotPayload:
    run_id: str
    strategy_id: str
    profile: ValidationProfile
    deterministic_checks: Mapping[str, str]
    evidence_refs: tuple[_SnapshotEvidenceRef, ...]
    requested_indicators: tuple[str, ...]


class AgentReviewToolExecutor(Protocol):
    """Tool execution boundary for evidence access."""

    def run(self, *, tool_name: str, evidence_ref: str) -> object:
        """Run a tool call and return structured payload."""


class InMemoryAgentReviewToolExecutor:
    """Deterministic tool executor backed by in-memory evidence payloads."""

    def __init__(self, payloads_by_ref: Mapping[str, object] | None = None) -> None:
        self._payloads_by_ref = dict(payloads_by_ref or {})

    def run(self, *, tool_name: str, evidence_ref: str) -> object:
        if tool_name != _ALLOWED_TOOL_NAME:
            raise ValueError(f"Unsupported tool: {tool_name!r}")
        return self._payloads_by_ref.get(evidence_ref, {})


class ValidationAgentReviewService:
    """Consumes compact snapshots and emits bounded-cost machine-readable findings."""

    DEFAULT_PROFILE_BUDGETS: dict[ValidationProfile, AgentReviewBudget] = {
        "FAST": AgentReviewBudget(
            max_runtime_seconds=0.35,
            max_tokens=600,
            max_tool_calls=1,
            max_findings=3,
        ),
        "STANDARD": AgentReviewBudget(
            max_runtime_seconds=1.2,
            max_tokens=2400,
            max_tool_calls=4,
            max_findings=6,
        ),
        "EXPERT": AgentReviewBudget(
            max_runtime_seconds=3.5,
            max_tokens=7200,
            max_tool_calls=8,
            max_findings=12,
        ),
    }

    def __init__(
        self,
        *,
        tool_executor: AgentReviewToolExecutor | None = None,
        profile_budgets: Mapping[ValidationProfile, AgentReviewBudget] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._tool_executor = tool_executor or InMemoryAgentReviewToolExecutor()
        self._budgets = self._normalize_profile_budgets(profile_budgets)
        self._clock = clock or time.monotonic

    def profile_budget(self, profile: ValidationProfile) -> AgentReviewBudget:
        return self._budgets[profile]

    def review(
        self,
        *,
        snapshot: Mapping[str, Any],
        tool_calls: Sequence[AgentReviewToolCall] | None = None,
    ) -> AgentReviewResult:
        parsed = self._parse_snapshot(snapshot=snapshot)
        budget = self.profile_budget(parsed.profile)
        started_at = self._clock()

        tokens_used = _estimate_tokens(snapshot)
        if tokens_used > budget.max_tokens:
            return self._breach_result(
                parsed=parsed,
                budget=budget,
                started_at=started_at,
                tokens_used=tokens_used,
                tool_calls_used=0,
                reason="token_budget_exceeded",
            )

        runtime_check = self._runtime_seconds(started_at=started_at)
        if runtime_check > budget.max_runtime_seconds:
            return self._breach_result(
                parsed=parsed,
                budget=budget,
                started_at=started_at,
                tokens_used=tokens_used,
                tool_calls_used=0,
                reason="runtime_budget_exceeded",
            )

        planned_tool_calls = (
            tuple(tool_calls) if tool_calls is not None else self._default_tool_calls(parsed=parsed, budget=budget)
        )

        if len(planned_tool_calls) > budget.max_tool_calls:
            return self._breach_result(
                parsed=parsed,
                budget=budget,
                started_at=started_at,
                tokens_used=tokens_used,
                tool_calls_used=0,
                reason="tool_budget_exceeded",
            )

        allowed_refs = {item.ref for item in parsed.evidence_refs}
        findings: list[AgentReviewFinding] = self._deterministic_findings(parsed=parsed)
        tool_calls_used = 0

        for call in planned_tool_calls:
            runtime_check = self._runtime_seconds(started_at=started_at)
            if runtime_check > budget.max_runtime_seconds:
                return self._breach_result(
                    parsed=parsed,
                    budget=budget,
                    started_at=started_at,
                    tokens_used=tokens_used,
                    tool_calls_used=tool_calls_used,
                    reason="runtime_budget_exceeded",
                )
            if call.tool_name not in _ALLOWED_TOOLS:
                return self._breach_result(
                    parsed=parsed,
                    budget=budget,
                    started_at=started_at,
                    tokens_used=tokens_used,
                    tool_calls_used=tool_calls_used,
                    reason="tool_not_allowed",
                )
            if call.evidence_ref not in allowed_refs:
                return self._breach_result(
                    parsed=parsed,
                    budget=budget,
                    started_at=started_at,
                    tokens_used=tokens_used,
                    tool_calls_used=tool_calls_used,
                    reason="tool_ref_out_of_scope",
                )

            tool_payload = self._tool_executor.run(tool_name=call.tool_name, evidence_ref=call.evidence_ref)
            tool_calls_used += 1
            tokens_used += _estimate_tokens(tool_payload)
            if tokens_used > budget.max_tokens:
                return self._breach_result(
                    parsed=parsed,
                    budget=budget,
                    started_at=started_at,
                    tokens_used=tokens_used,
                    tool_calls_used=tool_calls_used,
                    reason="token_budget_exceeded",
                )
            findings.extend(self._tool_payload_findings(evidence_ref=call.evidence_ref, payload=tool_payload))

        findings.extend(self._evidence_coverage_findings(parsed=parsed))
        findings = self._dedupe_findings(findings=findings, max_findings=budget.max_findings)

        status = self._resolve_decision(findings=findings)
        summary = self._build_summary(status=status, findings=findings)
        runtime_seconds = self._runtime_seconds(started_at=started_at)

        usage = AgentReviewBudgetUsage(
            runtime_seconds=runtime_seconds,
            tokens_used=tokens_used,
            tool_calls_used=tool_calls_used,
        )
        budget_report = AgentReviewBudgetReport(
            profile=parsed.profile,
            limits=budget,
            usage=usage,
            within_budget=True,
            breach_reason=None,
        )
        return AgentReviewResult(
            status=status,
            summary=summary,
            findings=tuple(findings),
            budget=budget_report,
        )

    def _normalize_profile_budgets(
        self,
        profile_budgets: Mapping[ValidationProfile, AgentReviewBudget] | None,
    ) -> dict[ValidationProfile, AgentReviewBudget]:
        source = profile_budgets or self.DEFAULT_PROFILE_BUDGETS
        normalized: dict[ValidationProfile, AgentReviewBudget] = {}
        for profile in _PROFILE_ORDER:
            if profile not in source:
                raise ValueError(f"Missing profile budget for {profile}.")
            normalized[profile] = source[profile]
        return normalized

    def _parse_snapshot(self, *, snapshot: Mapping[str, Any]) -> _SnapshotPayload:
        run_id = self._non_empty_string(snapshot.get("runId"), field_name="runId")
        strategy_id = self._non_empty_string(snapshot.get("strategyId"), field_name="strategyId")
        requested_indicators = self._parse_requested_indicators(snapshot=snapshot)
        policy = self._mapping(snapshot.get("policy"), field_name="policy")
        profile_raw = self._non_empty_string(policy.get("profile"), field_name="policy.profile")
        if profile_raw not in _PROFILE_ORDER:
            raise ValueError(f"Unsupported validation profile: {profile_raw!r}")
        profile = cast(ValidationProfile, profile_raw)
        deterministic_checks = self._parse_deterministic_checks(snapshot=snapshot)
        evidence_refs = self._parse_evidence_refs(snapshot=snapshot)
        return _SnapshotPayload(
            run_id=run_id,
            strategy_id=strategy_id,
            profile=profile,
            deterministic_checks=deterministic_checks,
            evidence_refs=evidence_refs,
            requested_indicators=requested_indicators,
        )

    def _parse_requested_indicators(self, *, snapshot: Mapping[str, Any]) -> tuple[str, ...]:
        raw = snapshot.get("requestedIndicators")
        if not isinstance(raw, list) or len(raw) == 0:
            raise ValueError("requestedIndicators must be a non-empty array.")
        indicators: list[str] = []
        for index, value in enumerate(raw):
            indicator = self._non_empty_string(value, field_name=f"requestedIndicators[{index}]")
            indicators.append(indicator)
        return tuple(indicators)

    def _parse_deterministic_checks(self, *, snapshot: Mapping[str, Any]) -> dict[str, str]:
        raw = self._mapping(snapshot.get("deterministicChecks"), field_name="deterministicChecks")
        fields = (
            "indicatorFidelityStatus",
            "tradeCoherenceStatus",
            "metricConsistencyStatus",
        )
        checks: dict[str, str] = {}
        for field in fields:
            value = self._non_empty_string(raw.get(field), field_name=f"deterministicChecks.{field}")
            if value not in {"pass", "fail"}:
                raise ValueError(f"deterministicChecks.{field} must be 'pass' or 'fail'.")
            checks[field] = value
        return checks

    def _parse_evidence_refs(self, *, snapshot: Mapping[str, Any]) -> tuple[_SnapshotEvidenceRef, ...]:
        raw = snapshot.get("evidenceRefs")
        if not isinstance(raw, list) or len(raw) == 0:
            raise ValueError("evidenceRefs must be a non-empty array.")
        refs: list[_SnapshotEvidenceRef] = []
        for index, item in enumerate(raw):
            mapping = self._mapping(item, field_name=f"evidenceRefs[{index}]")
            kind = self._non_empty_string(mapping.get("kind"), field_name=f"evidenceRefs[{index}].kind")
            ref = self._non_empty_string(mapping.get("ref"), field_name=f"evidenceRefs[{index}].ref")
            refs.append(_SnapshotEvidenceRef(kind=kind, ref=ref))
        return tuple(refs)

    def _mapping(self, value: object, *, field_name: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ValueError(f"{field_name} must be an object.")
        return cast(Mapping[str, Any], value)

    def _non_empty_string(self, value: object, *, field_name: str) -> str:
        if not isinstance(value, str) or value.strip() == "":
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value.strip()

    def _runtime_seconds(self, *, started_at: float) -> float:
        runtime = self._clock() - started_at
        if runtime < 0:
            return 0.0
        return runtime

    def _default_tool_calls(
        self,
        *,
        parsed: _SnapshotPayload,
        budget: AgentReviewBudget,
    ) -> tuple[AgentReviewToolCall, ...]:
        if parsed.profile == "FAST":
            return ()
        target_calls = min(
            len(parsed.evidence_refs),
            budget.max_tool_calls,
            2 if parsed.profile == "STANDARD" else budget.max_tool_calls,
        )
        calls: list[AgentReviewToolCall] = []
        for item in parsed.evidence_refs[:target_calls]:
            calls.append(AgentReviewToolCall(tool_name=_ALLOWED_TOOL_NAME, evidence_ref=item.ref))
        return tuple(calls)

    def _breach_result(
        self,
        *,
        parsed: _SnapshotPayload,
        budget: AgentReviewBudget,
        started_at: float,
        tokens_used: int,
        tool_calls_used: int,
        reason: str,
    ) -> AgentReviewResult:
        runtime_seconds = self._runtime_seconds(started_at=started_at)
        summary = f"Agent review blocked: {reason}."
        fallback_ref = parsed.evidence_refs[0].ref
        finding = AgentReviewFinding(
            id=f"agent-budget-{reason}",
            priority=0,
            confidence=1.0,
            summary=summary,
            evidence_refs=(fallback_ref,),
        )
        usage = AgentReviewBudgetUsage(
            runtime_seconds=runtime_seconds,
            tokens_used=max(tokens_used, 0),
            tool_calls_used=max(tool_calls_used, 0),
        )
        budget_report = AgentReviewBudgetReport(
            profile=parsed.profile,
            limits=budget,
            usage=usage,
            within_budget=False,
            breach_reason=reason,
        )
        return AgentReviewResult(
            status="fail",
            summary=summary,
            findings=(finding,),
            budget=budget_report,
        )

    def _deterministic_findings(self, *, parsed: _SnapshotPayload) -> list[AgentReviewFinding]:
        findings: list[AgentReviewFinding] = []
        check_to_finding = (
            ("indicatorFidelityStatus", 0, 0.99, "Deterministic indicator fidelity check failed."),
            ("tradeCoherenceStatus", 1, 0.96, "Deterministic trade coherence check failed."),
            ("metricConsistencyStatus", 2, 0.9, "Deterministic metric consistency check failed."),
        )
        refs = tuple(item.ref for item in parsed.evidence_refs[:2]) or (parsed.evidence_refs[0].ref,)
        for check_name, priority, confidence, message in check_to_finding:
            if parsed.deterministic_checks[check_name] == "fail":
                findings.append(
                    AgentReviewFinding(
                        id=f"agent-check-{check_name.lower()}",
                        priority=priority,
                        confidence=confidence,
                        summary=message,
                        evidence_refs=refs,
                    )
                )
        return findings

    def _evidence_coverage_findings(self, *, parsed: _SnapshotPayload) -> list[AgentReviewFinding]:
        if parsed.profile == "FAST":
            return []

        required_kinds = {"backtest_report", "trades", "execution_logs", "chart_payload"}
        present = {item.kind for item in parsed.evidence_refs}
        missing = sorted(required_kinds - present)
        if not missing:
            return []

        summary = "Missing evidence references required for bounded agent review: " + ", ".join(missing) + "."
        return [
            AgentReviewFinding(
                id="agent-evidence-coverage-missing",
                priority=1,
                confidence=0.93,
                summary=summary,
                evidence_refs=(parsed.evidence_refs[0].ref,),
            )
        ]

    def _tool_payload_findings(self, *, evidence_ref: str, payload: object) -> list[AgentReviewFinding]:
        findings: list[AgentReviewFinding] = []
        if isinstance(payload, Mapping):
            mapping = cast(Mapping[str, Any], payload)
            raw_error = mapping.get("error")
            if isinstance(raw_error, str) and raw_error.strip() != "":
                findings.append(
                    AgentReviewFinding(
                        id=f"agent-tool-error-{_stable_suffix(f'{evidence_ref}:{raw_error}')}",
                        priority=1,
                        confidence=0.88,
                        summary=f"Evidence tool reported error: {raw_error.strip()}",
                        evidence_refs=(evidence_ref,),
                    )
                )
            raw_status = mapping.get("status")
            if isinstance(raw_status, str) and raw_status.strip().lower() == "failed":
                findings.append(
                    AgentReviewFinding(
                        id=f"agent-tool-failed-{_stable_suffix(f'{evidence_ref}:{raw_status}')}",
                        priority=2,
                        confidence=0.79,
                        summary="Evidence payload indicates failed status.",
                        evidence_refs=(evidence_ref,),
                    )
                )
        if isinstance(payload, str):
            normalized = payload.strip().lower()
            if "error" in normalized or "exception" in normalized:
                findings.append(
                    AgentReviewFinding(
                        id=f"agent-tool-text-{_stable_suffix(f'{evidence_ref}:{normalized}')}",
                        priority=2,
                        confidence=0.72,
                        summary="Evidence text contains error markers.",
                        evidence_refs=(evidence_ref,),
                    )
                )
        return findings

    def _dedupe_findings(
        self,
        *,
        findings: Sequence[AgentReviewFinding],
        max_findings: int,
    ) -> list[AgentReviewFinding]:
        seen: set[str] = set()
        deduped: list[AgentReviewFinding] = []
        for finding in findings:
            signature = (
                finding.id,
                finding.priority,
                finding.confidence,
                finding.summary,
                tuple(finding.evidence_refs),
            )
            key = json.dumps(signature, sort_keys=False, separators=(",", ":"), default=str)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(finding)
            if len(deduped) >= max_findings:
                break
        return deduped

    def _resolve_decision(self, *, findings: Sequence[AgentReviewFinding]) -> ValidationDecision:
        if not findings:
            return "pass"
        if any(finding.priority <= 1 for finding in findings):
            return "fail"
        return "conditional_pass"

    def _build_summary(self, *, status: ValidationDecision, findings: Sequence[AgentReviewFinding]) -> str:
        if not findings and status == "pass":
            return "Agent review completed within profile budget with no blocking findings."
        if status == "fail":
            return f"Agent review found {len(findings)} blocking finding(s)."
        return f"Agent review completed with {len(findings)} advisory finding(s)."


__all__ = [
    "AgentReviewBudget",
    "AgentReviewBudgetReport",
    "AgentReviewBudgetUsage",
    "AgentReviewFinding",
    "AgentReviewResult",
    "AgentReviewToolCall",
    "AgentReviewToolExecutor",
    "InMemoryAgentReviewToolExecutor",
    "ValidationAgentReviewService",
    "ValidationDecision",
    "ValidationProfile",
]
