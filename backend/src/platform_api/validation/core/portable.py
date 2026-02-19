"""Portable validation orchestrator with explicit connector/store/render boundaries."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from src.platform_api.state_store import utc_now
from src.platform_api.validation.connectors.ports import (
    ConnectorRequestContext,
    ValidationConnector,
)
from src.platform_api.validation.core.agent_review import (
    AgentReviewResult,
    ValidationAgentReviewService,
)
from src.platform_api.validation.core.deterministic import (
    DeterministicValidationEngine,
    DeterministicValidationResult,
    ValidationPolicyConfig,
)
from src.platform_api.validation.render.ports import (
    NoopValidationRenderer,
    RenderedValidationArtifact,
    ValidationRenderFormat,
    ValidationRenderPort,
)
from src.platform_api.validation.store.ports import (
    ValidationFinalDecision,
    ValidationStorePort,
    ValidationStoreRecord,
)

PortableValidationDecision = Literal["pass", "conditional_pass", "fail"]


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _findings_payload(agent_result: AgentReviewResult) -> list[dict[str, Any]]:
    return [finding.to_contract_payload() for finding in agent_result.findings]


@dataclass(frozen=True)
class PortableValidationResult:
    """Portable validation output payload and lane results."""

    artifact: dict[str, Any]
    snapshot: dict[str, Any]
    deterministic_result: DeterministicValidationResult
    agent_result: AgentReviewResult
    rendered_artifacts: tuple[RenderedValidationArtifact, ...]


class PortableValidationModule:
    """Executes validation core with connector/store/render boundary ports."""

    def __init__(
        self,
        *,
        connector: ValidationConnector,
        store: ValidationStorePort | None = None,
        renderer: ValidationRenderPort | None = None,
        deterministic_engine: DeterministicValidationEngine | None = None,
        agent_review_service: ValidationAgentReviewService | None = None,
    ) -> None:
        self._connector = connector
        self._store = store
        self._renderer = renderer or NoopValidationRenderer()
        self._deterministic_engine = deterministic_engine or DeterministicValidationEngine()
        self._agent_review_service = agent_review_service or ValidationAgentReviewService()

    async def run(
        self,
        *,
        run_id: str,
        request_id: str,
        tenant_id: str,
        user_id: str,
        payload: Mapping[str, Any],
        policy_payload: Mapping[str, Any],
        created_at: str | None = None,
        render_formats: Sequence[ValidationRenderFormat] = (),
        persist: bool = True,
    ) -> PortableValidationResult:
        connector_payload = self._connector.resolve(
            context=ConnectorRequestContext(
                run_id=run_id,
                request_id=request_id,
                tenant_id=tenant_id,
                user_id=user_id,
            ),
            payload=payload,
        )
        policy = ValidationPolicyConfig.from_contract_payload(dict(policy_payload))

        deterministic_result = self._deterministic_engine.evaluate(
            evidence=connector_payload.evidence,
            policy=policy,
        )
        artifact = self._deterministic_engine.build_canonical_artifact(
            context=connector_payload.artifact_context,
            result=deterministic_result,
            policy=policy,
            created_at=created_at,
        )
        generated_at = created_at or utc_now()
        snapshot = self._build_snapshot(artifact=artifact, generated_at=generated_at)

        agent_result = self._agent_review_service.review(snapshot=snapshot, tool_calls=())
        artifact["agentReview"] = {
            "status": agent_result.status,
            "summary": agent_result.summary,
            "findings": _findings_payload(agent_result),
        }
        final_decision = self._resolve_final_decision(
            deterministic_status=deterministic_result.final_decision,
            agent_status=agent_result.status,
            policy=policy,
        )
        artifact["finalDecision"] = final_decision
        snapshot["finalDecision"] = final_decision
        snapshot["findings"] = [
            {
                "priority": finding.priority,
                "confidence": finding.confidence,
                "summary": finding.summary,
            }
            for finding in agent_result.findings
        ]

        if persist and self._store is not None:
            await self._store.persist(
                ValidationStoreRecord(
                    run_id=run_id,
                    request_id=request_id,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    profile=policy.profile,
                    final_decision=final_decision,
                    artifact_ref=f"blob://validation/{run_id}/validation-run.json",
                    artifact=copy.deepcopy(artifact),
                    snapshot=copy.deepcopy(snapshot),
                    agent_review=copy.deepcopy(artifact["agentReview"]),
                    created_at=generated_at,
                )
            )

        rendered_artifacts: list[RenderedValidationArtifact] = []
        for output_format in render_formats:
            rendered = self._renderer.render(artifact=artifact, output_format=output_format)
            if rendered is not None:
                rendered_artifacts.append(rendered)

        return PortableValidationResult(
            artifact=artifact,
            snapshot=snapshot,
            deterministic_result=deterministic_result,
            agent_result=agent_result,
            rendered_artifacts=tuple(rendered_artifacts),
        )

    def _build_snapshot(self, *, artifact: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
        checks = _mapping(artifact.get("deterministicChecks"))
        indicator = _mapping(checks.get("indicatorFidelity"))
        trade = _mapping(checks.get("tradeCoherence"))
        metric = _mapping(checks.get("metricConsistency"))
        outputs = _mapping(artifact.get("outputs"))
        strategy_ref = _mapping(artifact.get("strategyRef"))
        inputs = _mapping(artifact.get("inputs"))

        evidence_refs: list[dict[str, str]] = []
        for kind, field in (
            ("strategy_code", "strategyCodeRef"),
            ("backtest_report", "backtestReportRef"),
            ("trades", "tradesRef"),
            ("execution_logs", "executionLogsRef"),
            ("chart_payload", "chartPayloadRef"),
        ):
            raw_ref = outputs.get(field)
            if isinstance(raw_ref, str) and raw_ref.strip() != "":
                evidence_refs.append({"kind": kind, "ref": raw_ref})

        return {
            "schemaVersion": "validation-llm-snapshot.v1",
            "runId": artifact.get("runId"),
            "sourceSchemaVersion": artifact.get("schemaVersion"),
            "generatedAt": generated_at,
            "strategyId": strategy_ref.get("strategyId"),
            "requestedIndicators": list(inputs.get("requestedIndicators", [])),
            "deterministicChecks": {
                "indicatorFidelityStatus": indicator.get("status", "fail"),
                "tradeCoherenceStatus": trade.get("status", "fail"),
                "metricConsistencyStatus": metric.get("status", "fail"),
            },
            "policy": dict(_mapping(artifact.get("policy"))),
            "evidenceRefs": evidence_refs,
            "finalDecision": artifact.get("finalDecision", "fail"),
        }

    def _resolve_final_decision(
        self,
        *,
        deterministic_status: str,
        agent_status: str,
        policy: ValidationPolicyConfig,
    ) -> ValidationFinalDecision:
        if deterministic_status == "fail":
            return "fail"

        if agent_status == "fail":
            if policy.block_merge_on_agent_fail:
                return "fail"
            return "conditional_pass"

        if policy.require_trader_review:
            return "conditional_pass"

        if agent_status == "conditional_pass":
            return "conditional_pass"

        return "pass"


__all__ = [
    "PortableValidationDecision",
    "PortableValidationModule",
    "PortableValidationResult",
]
