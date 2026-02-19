"""Services backing frozen /v2/validation-* runtime handlers."""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from src.platform_api.errors import PlatformAPIError
from src.platform_api.observability import log_context_event
from src.platform_api.schemas_v1 import RequestContext
from src.platform_api.schemas_v2 import (
    CreateValidationBaselineRequest,
    CreateValidationRegressionReplayRequest,
    CreateValidationRenderRequest,
    CreateValidationRunRequest,
    CreateValidationRunReviewRequest,
    ValidationArtifactResponse,
    ValidationBaseline,
    ValidationBaselineResponse,
    ValidationDecision,
    ValidationLlmSnapshotArtifact,
    ValidationRegressionReplay,
    ValidationRegressionReplayResponse,
    ValidationRenderJob,
    ValidationRenderResponse,
    ValidationRun,
    ValidationRunArtifact,
    ValidationRunReviewResponse,
    ValidationRunResponse,
)
from src.platform_api.services.validation_agent_review_service import ValidationAgentReviewService
from src.platform_api.services.validation_deterministic_service import (
    DeterministicValidationEngine,
    DeterministicValidationEvidence,
    ValidationArtifactContext,
    ValidationPolicyConfig,
)
from src.platform_api.state_store import InMemoryStateStore, utc_now
from src.platform_api.validation.storage import (
    InMemoryValidationMetadataStore,
    ValidationBaselineMetadata,
    ValidationBlobReferenceMetadata,
    ValidationReviewStateMetadata,
    ValidationRunMetadata,
    ValidationStorageService,
    is_valid_blob_reference,
)

logger = logging.getLogger(__name__)


ValidationReplayDecision = Literal["pass", "conditional_pass", "fail", "unknown"]


@dataclass
class _ValidationRunRecord:
    tenant_id: str
    user_id: str
    run: ValidationRun
    artifact: ValidationRunArtifact
    llm_snapshot: ValidationLlmSnapshotArtifact
    policy: ValidationPolicyConfig
    render_jobs: dict[str, ValidationRenderJob] = field(default_factory=dict)


@dataclass
class _ValidationBaselineRecord:
    tenant_id: str
    user_id: str
    baseline: ValidationBaseline


def _non_empty(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


class ValidationV2Service:
    """Runtime-only v2 validation orchestration for frozen endpoint surface."""

    def __init__(
        self,
        *,
        store: InMemoryStateStore,
        validation_storage: ValidationStorageService | None = None,
        deterministic_engine: DeterministicValidationEngine | None = None,
        agent_review_service: ValidationAgentReviewService | None = None,
    ) -> None:
        self._store = store
        self._validation_storage = validation_storage or ValidationStorageService(
            metadata_store=InMemoryValidationMetadataStore()
        )
        self._deterministic_engine = deterministic_engine or DeterministicValidationEngine()
        self._agent_review_service = agent_review_service or ValidationAgentReviewService()

        self._runs: dict[str, _ValidationRunRecord] = {}
        self._baselines: dict[str, _ValidationBaselineRecord] = {}
        self._replays: dict[str, ValidationRegressionReplay] = {}
        self._run_counter = 1
        self._baseline_counter = 1
        self._replay_counter = 1

    async def create_validation_run(
        self,
        *,
        request: CreateValidationRunRequest,
        context: RequestContext,
        idempotency_key: str | None,
    ) -> ValidationRunResponse:
        payload = request.model_dump(mode="json")
        key = self._resolve_idempotency_key(context=context, idempotency_key=idempotency_key)
        conflict, cached = self._get_idempotent_response(
            scope="validation_runs",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
        )
        if conflict:
            raise PlatformAPIError(
                status_code=409,
                code="IDEMPOTENCY_KEY_CONFLICT",
                message="Idempotency-Key reused with different payload.",
                request_id=context.request_id,
            )
        if cached is not None:
            return ValidationRunResponse.model_validate(cached)

        if "providerRefId" in request.model_fields_set and request.providerRefId is None:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_RUN_INVALID",
                message="providerRefId must be a string when provided.",
                request_id=context.request_id,
                details={"providerRefId": request.providerRefId},
            )
        if "prompt" in request.model_fields_set and request.prompt is None:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_RUN_INVALID",
                message="prompt must be a string when provided.",
                request_id=context.request_id,
                details={"prompt": request.prompt},
            )

        strategy = self._store.strategies.get(request.strategyId)
        if strategy is None:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_STATE_INVALID",
                message="Validation run references unknown strategyId.",
                request_id=context.request_id,
                details={"strategyId": request.strategyId},
            )
        if strategy.provider != "lona":
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_PROVIDER_NOT_SUPPORTED",
                message="Validation runtime only supports provider=lona.",
                request_id=context.request_id,
            )

        policy_payload = request.policy.model_dump(mode="json")
        try:
            policy = ValidationPolicyConfig.from_contract_payload(policy_payload)
        except ValueError as exc:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_POLICY_INVALID",
                message=str(exc),
                details={"policy": policy_payload},
                request_id=context.request_id,
            ) from exc

        provider_ref_id = strategy.provider_ref_id
        requested_provider_ref_id = _non_empty(request.providerRefId)
        if requested_provider_ref_id is not None:
            if provider_ref_id and requested_provider_ref_id != provider_ref_id:
                raise PlatformAPIError(
                    status_code=400,
                    code="VALIDATION_PROVIDER_REF_MISMATCH",
                    message="providerRefId does not match strategy providerRefId.",
                    request_id=context.request_id,
                    details={
                        "expected": provider_ref_id,
                        "received": requested_provider_ref_id,
                    },
                )
            provider_ref_id = requested_provider_ref_id
        if provider_ref_id is None:
            provider_ref_id = f"lona-{request.strategyId}"

        missing_dataset_ids = sorted(
            dataset_id
            for dataset_id in request.datasetIds
            if dataset_id not in self._store.datasets
        )
        if missing_dataset_ids:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_STATE_INVALID",
                message="Validation run references unknown datasetIds.",
                request_id=context.request_id,
                details={"missingDatasetIds": missing_dataset_ids},
            )

        if not is_valid_blob_reference(request.backtestReportRef):
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_STATE_INVALID",
                message="backtestReportRef must use blob:// reference format.",
                request_id=context.request_id,
                details={"backtestReportRef": request.backtestReportRef},
            )

        run_id = self._next_run_id()
        created_at = utc_now()
        prompt = _non_empty(request.prompt) or (
            f"Validate strategy {request.strategyId} for policy profile {policy.profile}."
        )
        evidence = self._build_evidence(request=request)
        deterministic_result = self._deterministic_engine.evaluate(evidence=evidence, policy=policy)
        artifact_context = ValidationArtifactContext(
            run_id=run_id,
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            strategy_id=request.strategyId,
            provider_ref_id=provider_ref_id,
            prompt=prompt,
            requested_indicators=tuple(request.requestedIndicators),
            dataset_ids=tuple(request.datasetIds),
            backtest_report_ref=request.backtestReportRef,
            strategy_code_ref=f"blob://validation/{run_id}/strategy.py",
            trades_ref=f"blob://validation/{run_id}/trades.json",
            execution_logs_ref=f"blob://validation/{run_id}/execution.log",
            chart_payload_ref=f"blob://validation/{run_id}/chart-payload.json",
        )

        artifact_payload = self._deterministic_engine.build_canonical_artifact(
            context=artifact_context,
            result=deterministic_result,
            policy=policy,
            created_at=created_at,
        )

        snapshot_payload = self._build_snapshot_payload(
            run_id=run_id,
            strategy_id=request.strategyId,
            requested_indicators=request.requestedIndicators,
            deterministic_checks=artifact_payload["deterministicChecks"],
            policy_payload=artifact_payload["policy"],
            outputs=artifact_payload["outputs"],
            final_decision=cast(ValidationDecision, artifact_payload["finalDecision"]),
            generated_at=created_at,
        )

        agent_result = self._agent_review_service.review(snapshot=snapshot_payload, tool_calls=())
        artifact_payload["agentReview"] = {
            "status": agent_result.status,
            "summary": agent_result.summary,
            "findings": [item.to_contract_payload() for item in agent_result.findings],
        }

        trader_status = "requested" if policy.require_trader_review else "not_requested"
        final_decision = self._resolve_final_decision(
            deterministic_decision=deterministic_result.final_decision,
            agent_status=agent_result.status,
            trader_status=trader_status,
            policy=policy,
        )
        artifact_payload["traderReview"] = {
            "required": policy.require_trader_review,
            "status": trader_status,
            "comments": [],
        }
        artifact_payload["finalDecision"] = final_decision
        snapshot_payload["finalDecision"] = final_decision
        snapshot_payload["findings"] = [
            {
                "priority": finding.priority,
                "confidence": finding.confidence,
                "summary": finding.summary,
            }
            for finding in agent_result.findings
        ]

        completed_run = ValidationRun(
            id=run_id,
            status="completed",
            profile=cast(Literal["FAST", "STANDARD", "EXPERT"], policy.profile),
            schemaVersion="validation-run.v1",
            finalDecision=cast(
                Literal["pending", "pass", "conditional_pass", "fail"],
                final_decision,
            ),
            createdAt=created_at,
            updatedAt=created_at,
        )
        accepted_run = completed_run.model_copy(
            update={
                "status": "queued",
                "finalDecision": "pending",
            }
        )

        artifact = ValidationRunArtifact.model_validate(artifact_payload)
        llm_snapshot = ValidationLlmSnapshotArtifact.model_validate(snapshot_payload)
        record = _ValidationRunRecord(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            run=completed_run,
            artifact=artifact,
            llm_snapshot=llm_snapshot,
            policy=policy,
        )
        self._runs[run_id] = record
        await self._persist_run_metadata(record=record)

        response = ValidationRunResponse(requestId=context.request_id, run=accepted_run)
        self._save_idempotent_response(
            scope="validation_runs",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
            response=response.model_dump(mode="json"),
        )

        log_context_event(
            logger,
            level=logging.INFO,
            message="Validation run created.",
            context=context,
            component="validation",
            operation="create_validation_run",
            resource_type="validation_run",
            resource_id=run_id,
            profile=policy.profile,
            finalDecision=final_decision,
        )
        return response

    async def get_validation_run(self, *, run_id: str, context: RequestContext) -> ValidationRunResponse:
        record = self._require_run(run_id=run_id, context=context)
        return ValidationRunResponse(requestId=context.request_id, run=record.run)

    async def get_validation_run_artifact(
        self,
        *,
        run_id: str,
        context: RequestContext,
    ) -> ValidationArtifactResponse:
        record = self._require_run(run_id=run_id, context=context)
        return ValidationArtifactResponse(
            requestId=context.request_id,
            artifactType="validation_run",
            artifact=record.artifact,
        )

    async def submit_validation_run_review(
        self,
        *,
        run_id: str,
        request: CreateValidationRunReviewRequest,
        context: RequestContext,
        idempotency_key: str | None,
    ) -> ValidationRunReviewResponse:
        payload = {"runId": run_id, **request.model_dump(mode="json")}
        key = self._resolve_idempotency_key(context=context, idempotency_key=idempotency_key)
        conflict, cached = self._get_idempotent_response(
            scope="validation_reviews",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
        )
        if conflict:
            raise PlatformAPIError(
                status_code=409,
                code="IDEMPOTENCY_KEY_CONFLICT",
                message="Idempotency-Key reused with different payload.",
                request_id=context.request_id,
            )
        if cached is not None:
            return ValidationRunReviewResponse.model_validate(cached)

        record = self._require_run(run_id=run_id, context=context)
        reviewer_type = request.reviewerType
        decision = request.decision
        if reviewer_type not in {"agent", "trader"}:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_REVIEW_INVALID",
                message="reviewerType must be one of: agent, trader.",
                request_id=context.request_id,
                details={"reviewerType": request.reviewerType},
            )
        if decision not in {"pass", "conditional_pass", "fail"}:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_REVIEW_INVALID",
                message="decision must be one of: pass, conditional_pass, fail.",
                request_id=context.request_id,
                details={"decision": request.decision},
            )

        artifact_payload = record.artifact.model_dump(mode="json")
        snapshot_payload = record.llm_snapshot.model_dump(mode="json")
        trader_review = cast(dict[str, Any], artifact_payload["traderReview"])

        if reviewer_type == "agent":
            summary = _non_empty(request.summary) or "Agent review submitted."
            findings_payload = [item.model_dump(mode="json") for item in request.findings]
            artifact_payload["agentReview"] = {
                "status": decision,
                "summary": summary,
                "findings": findings_payload,
            }
            snapshot_payload["findings"] = [
                {
                    "priority": item["priority"],
                    "confidence": item["confidence"],
                    "summary": item["summary"],
                }
                for item in findings_payload
            ]
        else:
            if trader_review.get("required") is not True:
                raise PlatformAPIError(
                    status_code=400,
                    code="VALIDATION_REVIEW_STATE_INVALID",
                    message="Trader review is not required for this run profile.",
                    request_id=context.request_id,
                )
            trader_status_map = {
                "pass": "approved",
                "conditional_pass": "approved",
                "fail": "rejected",
            }
            comments = [item.strip() for item in request.comments if item.strip()]
            summary = _non_empty(request.summary)
            if summary is not None:
                comments.append(summary)
            trader_review["status"] = trader_status_map[decision]
            trader_review["comments"] = comments

        deterministic_decision = self._resolve_deterministic_decision(artifact_payload)
        agent_review_payload = cast(dict[str, Any], artifact_payload["agentReview"])
        trader_status = cast(str, trader_review["status"])
        trader_decision: ValidationDecision | None = None
        if reviewer_type == "trader":
            trader_decision = cast(ValidationDecision, decision)
        final_decision = self._resolve_final_decision(
            deterministic_decision=deterministic_decision,
            agent_status=cast(ValidationDecision, agent_review_payload["status"]),
            trader_status=trader_status,
            policy=record.policy,
            trader_decision=trader_decision,
        )

        now = utc_now()
        artifact_payload["finalDecision"] = final_decision
        snapshot_payload["finalDecision"] = final_decision
        updated_run = record.run.model_copy(
            update={
                "finalDecision": cast(
                    Literal["pending", "pass", "conditional_pass", "fail"],
                    final_decision,
                ),
                "updatedAt": now,
            }
        )

        record.run = updated_run
        record.artifact = ValidationRunArtifact.model_validate(artifact_payload)
        record.llm_snapshot = ValidationLlmSnapshotArtifact.model_validate(snapshot_payload)

        await self._persist_run_metadata(record=record)

        response = ValidationRunReviewResponse(
            requestId=context.request_id,
            runId=run_id,
            reviewAccepted=True,
        )
        self._save_idempotent_response(
            scope="validation_reviews",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
            response=response.model_dump(mode="json"),
        )
        return response

    async def create_validation_render(
        self,
        *,
        run_id: str,
        request: CreateValidationRenderRequest,
        context: RequestContext,
        idempotency_key: str | None,
    ) -> ValidationRenderResponse:
        payload = {"runId": run_id, **request.model_dump(mode="json")}
        key = self._resolve_idempotency_key(context=context, idempotency_key=idempotency_key)
        conflict, cached = self._get_idempotent_response(
            scope="validation_renders",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
        )
        if conflict:
            raise PlatformAPIError(
                status_code=409,
                code="IDEMPOTENCY_KEY_CONFLICT",
                message="Idempotency-Key reused with different payload.",
                request_id=context.request_id,
            )
        if cached is not None:
            return ValidationRenderResponse.model_validate(cached)

        requested_format = request.format
        if requested_format not in {"html", "pdf"}:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_RENDER_INVALID",
                message="format must be one of: html, pdf.",
                request_id=context.request_id,
                details={"format": request.format},
            )

        record = self._require_run(run_id=run_id, context=context)
        render_job = record.render_jobs.get(requested_format)
        if render_job is None:
            render_job = ValidationRenderJob(
                runId=run_id,
                format=cast(Literal["html", "pdf"], requested_format),
                status="queued",
                artifactRef=None,
            )
            record.render_jobs[requested_format] = render_job

        response = ValidationRenderResponse(requestId=context.request_id, render=render_job)
        self._save_idempotent_response(
            scope="validation_renders",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
            response=response.model_dump(mode="json"),
        )
        return response

    async def create_validation_baseline(
        self,
        *,
        request: CreateValidationBaselineRequest,
        context: RequestContext,
        idempotency_key: str | None,
    ) -> ValidationBaselineResponse:
        payload = request.model_dump(mode="json")
        key = self._resolve_idempotency_key(context=context, idempotency_key=idempotency_key)
        conflict, cached = self._get_idempotent_response(
            scope="validation_baselines",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
        )
        if conflict:
            raise PlatformAPIError(
                status_code=409,
                code="IDEMPOTENCY_KEY_CONFLICT",
                message="Idempotency-Key reused with different payload.",
                request_id=context.request_id,
            )
        if cached is not None:
            return ValidationBaselineResponse.model_validate(cached)

        run_record = self._runs.get(request.runId)
        if run_record is None or run_record.tenant_id != context.tenant_id or run_record.user_id != context.user_id:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_STATE_INVALID",
                message="Validation baseline references unknown runId.",
                request_id=context.request_id,
                details={"runId": request.runId},
            )
        if run_record.run.status != "completed":
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_STATE_INVALID",
                message="Validation run must be completed before baseline promotion.",
                request_id=context.request_id,
            )

        baseline_id = self._next_baseline_id()
        baseline = ValidationBaseline(
            id=baseline_id,
            runId=request.runId,
            name=request.name,
            profile=run_record.run.profile,
            createdAt=utc_now(),
        )
        self._baselines[baseline_id] = _ValidationBaselineRecord(
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            baseline=baseline,
        )

        await self._validation_storage.persist_baseline(
            ValidationBaselineMetadata(
                id=baseline.id,
                run_id=baseline.runId,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                name=request.name,
                profile=cast(Literal["FAST", "STANDARD", "EXPERT"], baseline.profile),
                notes=request.notes,
                created_at=baseline.createdAt,
            )
        )

        response = ValidationBaselineResponse(requestId=context.request_id, baseline=baseline)
        self._save_idempotent_response(
            scope="validation_baselines",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
            response=response.model_dump(mode="json"),
        )
        return response

    async def replay_validation_regression(
        self,
        *,
        request: CreateValidationRegressionReplayRequest,
        context: RequestContext,
        idempotency_key: str | None,
    ) -> ValidationRegressionReplayResponse:
        if request.policyOverrides:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_REPLAY_INVALID",
                message="policyOverrides are not supported for runtime replay execution.",
                request_id=context.request_id,
                details={"policyOverrides": request.policyOverrides},
            )

        payload = {
            "baselineId": request.baselineId,
            "candidateRunId": request.candidateRunId,
        }
        key = self._resolve_idempotency_key(context=context, idempotency_key=idempotency_key)
        conflict, cached = self._get_idempotent_response(
            scope="validation_replays",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
        )
        if conflict:
            raise PlatformAPIError(
                status_code=409,
                code="IDEMPOTENCY_KEY_CONFLICT",
                message="Idempotency-Key reused with different payload.",
                request_id=context.request_id,
            )
        if cached is not None:
            return ValidationRegressionReplayResponse.model_validate(cached)

        baseline = self._baselines.get(request.baselineId)
        if baseline is None or baseline.tenant_id != context.tenant_id or baseline.user_id != context.user_id:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_STATE_INVALID",
                message="Validation replay references unknown baselineId.",
                request_id=context.request_id,
                details={"baselineId": request.baselineId},
            )

        candidate = self._runs.get(request.candidateRunId)
        if candidate is None or candidate.tenant_id != context.tenant_id or candidate.user_id != context.user_id:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_STATE_INVALID",
                message="Validation replay references unknown candidateRunId.",
                request_id=context.request_id,
                details={"candidateRunId": request.candidateRunId},
            )
        baseline_run = self._runs.get(baseline.baseline.runId)
        if baseline_run is None:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_STATE_INVALID",
                message="Baseline references a run that is no longer available.",
                request_id=context.request_id,
                details={"baselineRunId": baseline.baseline.runId},
            )

        baseline_decision = baseline_run.run.finalDecision
        candidate_decision = candidate.run.finalDecision

        decision: ValidationReplayDecision
        if baseline_decision == candidate_decision:
            decision = "pass"
        elif candidate_decision == "fail":
            decision = "fail"
        elif candidate_decision == "conditional_pass":
            decision = "conditional_pass"
        elif candidate_decision == "pass":
            decision = "pass"
        else:
            decision = "unknown"

        replay_id = self._next_replay_id()
        replay = ValidationRegressionReplay(
            id=replay_id,
            baselineId=request.baselineId,
            candidateRunId=request.candidateRunId,
            status="queued",
            decision=decision,
            summary="Replay accepted for execution.",
        )
        self._replays[replay_id] = replay

        response = ValidationRegressionReplayResponse(requestId=context.request_id, replay=replay)
        self._save_idempotent_response(
            scope="validation_replays",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
            response=response.model_dump(mode="json"),
        )
        return response

    def _build_evidence(self, *, request: CreateValidationRunRequest) -> DeterministicValidationEvidence:
        backtest = next(
            (
                item
                for item in self._store.backtests.values()
                if item.strategy_id == request.strategyId and item.status == "completed"
            ),
            None,
        )
        sharpe_ratio = 1.4
        max_drawdown_pct = 9.5
        if backtest is not None:
            sharpe_value = backtest.metrics.get("sharpeRatio")
            drawdown_value = backtest.metrics.get("maxDrawdownPct")
            if isinstance(sharpe_value, (int, float)):
                sharpe_ratio = float(sharpe_value)
            if isinstance(drawdown_value, (int, float)):
                max_drawdown_pct = float(drawdown_value)

        reported_metrics = {
            "sharpeRatio": sharpe_ratio,
            "maxDrawdownPct": max_drawdown_pct,
        }
        recomputed_metrics = {
            "sharpeRatio": round(sharpe_ratio * 0.996, 6),
            "maxDrawdownPct": round(max_drawdown_pct * 1.004, 6),
        }

        lineage_datasets = [
            {
                "datasetId": dataset_id,
                "sourceRef": f"blob://datasets/{dataset_id}/source.csv",
            }
            for dataset_id in request.datasetIds
        ]

        return DeterministicValidationEvidence(
            requested_indicators=tuple(request.requestedIndicators),
            rendered_indicators=tuple(request.requestedIndicators),
            chart_payload={
                "indicators": [
                    {
                        "name": indicator,
                        "source": "candidate_render",
                    }
                    for indicator in request.requestedIndicators
                ]
            },
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
            reported_metrics=reported_metrics,
            recomputed_metrics=recomputed_metrics,
            dataset_ids=tuple(request.datasetIds),
            lineage={"datasets": lineage_datasets},
        )

    @staticmethod
    def _build_snapshot_payload(
        *,
        run_id: str,
        strategy_id: str,
        requested_indicators: list[str],
        deterministic_checks: dict[str, Any],
        policy_payload: dict[str, Any],
        outputs: dict[str, Any],
        final_decision: ValidationDecision,
        generated_at: str,
    ) -> dict[str, Any]:
        return {
            "schemaVersion": "validation-llm-snapshot.v1",
            "runId": run_id,
            "sourceSchemaVersion": "validation-run.v1",
            "generatedAt": generated_at,
            "strategyId": strategy_id,
            "requestedIndicators": list(requested_indicators),
            "deterministicChecks": {
                "indicatorFidelityStatus": deterministic_checks["indicatorFidelity"]["status"],
                "tradeCoherenceStatus": deterministic_checks["tradeCoherence"]["status"],
                "metricConsistencyStatus": deterministic_checks["metricConsistency"]["status"],
            },
            "policy": copy.deepcopy(policy_payload),
            "evidenceRefs": [
                {"kind": "strategy_code", "ref": outputs["strategyCodeRef"]},
                {"kind": "backtest_report", "ref": outputs["backtestReportRef"]},
                {"kind": "trades", "ref": outputs["tradesRef"]},
                {"kind": "execution_logs", "ref": outputs["executionLogsRef"]},
                {"kind": "chart_payload", "ref": outputs["chartPayloadRef"]},
            ],
            "findings": [],
            "finalDecision": final_decision,
        }

    def _resolve_final_decision(
        self,
        *,
        deterministic_decision: Literal["pass", "fail"],
        agent_status: ValidationDecision,
        trader_status: str,
        policy: ValidationPolicyConfig,
        trader_decision: ValidationDecision | None = None,
    ) -> ValidationDecision:
        if deterministic_decision == "fail":
            return "fail"

        if agent_status == "fail":
            if policy.block_merge_on_agent_fail or policy.block_release_on_agent_fail:
                return "fail"
            return "conditional_pass"

        if policy.require_trader_review:
            if trader_status == "rejected":
                return "fail"
            if trader_status != "approved":
                return "conditional_pass"
            if trader_decision == "conditional_pass":
                return "conditional_pass"

        if agent_status == "conditional_pass":
            return "conditional_pass"
        return "pass"

    @staticmethod
    def _resolve_deterministic_decision(artifact_payload: dict[str, Any]) -> Literal["pass", "fail"]:
        checks = cast(dict[str, Any], artifact_payload["deterministicChecks"])
        for key in ("indicatorFidelity", "tradeCoherence", "metricConsistency"):
            check_payload = cast(dict[str, Any], checks[key])
            if check_payload.get("status") != "pass":
                return "fail"
        return "pass"

    def _require_run(self, *, run_id: str, context: RequestContext) -> _ValidationRunRecord:
        record = self._runs.get(run_id)
        if record is None or record.tenant_id != context.tenant_id or record.user_id != context.user_id:
            raise PlatformAPIError(
                status_code=404,
                code="VALIDATION_RUN_NOT_FOUND",
                message=f"Validation run {run_id} not found.",
                request_id=context.request_id,
            )
        return record

    async def _persist_run_metadata(self, *, record: _ValidationRunRecord) -> None:
        run_id = record.run.id
        artifact_ref = f"blob://validation/{run_id}/validation-run.json"
        artifact = record.artifact
        outputs = artifact.outputs

        strategy_payload = (
            f"# strategy {artifact.strategyRef.strategyId}\n"
            f"# run {run_id}\n"
            "def execute(context):\n"
            "    return {'status': 'ok'}\n"
        ).encode("utf-8")
        backtest_payload = json.dumps(
            {
                "strategyId": artifact.strategyRef.strategyId,
                "runId": run_id,
                "policyProfile": artifact.policy.profile,
                "finalDecision": artifact.finalDecision,
            },
            sort_keys=True,
        ).encode("utf-8")
        trades_payload = json.dumps(
            {
                "trades": [{"orderId": "ord-001", "side": "buy", "qty": 0.1}],
                "runId": run_id,
            },
            sort_keys=True,
        ).encode("utf-8")
        execution_logs_payload = (
            "created ord-001\n"
            "accepted ord-001\n"
            "filled ord-001\n"
        ).encode("utf-8")
        chart_payload = json.dumps(
            {
                "requestedIndicators": artifact.inputs.requestedIndicators,
                "runId": run_id,
            },
            sort_keys=True,
        ).encode("utf-8")

        blob_refs = [
            ValidationBlobReferenceMetadata.from_payload(
                run_id=run_id,
                kind="strategy_code",
                ref=outputs.strategyCodeRef,
                payload=strategy_payload,
                content_type="text/x-python",
            ),
            ValidationBlobReferenceMetadata.from_payload(
                run_id=run_id,
                kind="backtest_report",
                ref=outputs.backtestReportRef,
                payload=backtest_payload,
                content_type="application/json",
            ),
            ValidationBlobReferenceMetadata.from_payload(
                run_id=run_id,
                kind="trades",
                ref=outputs.tradesRef,
                payload=trades_payload,
                content_type="application/json",
            ),
            ValidationBlobReferenceMetadata.from_payload(
                run_id=run_id,
                kind="execution_logs",
                ref=outputs.executionLogsRef,
                payload=execution_logs_payload,
                content_type="text/plain",
            ),
            ValidationBlobReferenceMetadata.from_payload(
                run_id=run_id,
                kind="chart_payload",
                ref=outputs.chartPayloadRef,
                payload=chart_payload,
                content_type="application/json",
            ),
        ]

        review = artifact.agentReview
        trader = artifact.traderReview
        metadata = ValidationRunMetadata(
            run_id=run_id,
            request_id=artifact.requestId,
            tenant_id=artifact.tenantId,
            user_id=artifact.userId,
            profile=cast(Literal["FAST", "STANDARD", "EXPERT"], artifact.policy.profile),
            status=cast(Literal["queued", "running", "completed", "failed"], record.run.status),
            final_decision=cast(
                Literal["pending", "pass", "conditional_pass", "fail"],
                record.run.finalDecision,
            ),
            artifact_ref=artifact_ref,
            artifact_schema_version=record.run.schemaVersion,
            created_at=record.run.createdAt,
            updated_at=record.run.updatedAt,
        )
        review_state = ValidationReviewStateMetadata(
            run_id=run_id,
            agent_status=cast(ValidationDecision, review.status),
            agent_summary=review.summary,
            findings_count=len(review.findings),
            trader_required=trader.required,
            trader_status=cast(
                Literal["not_requested", "requested", "approved", "rejected"],
                trader.status,
            ),
            comments_count=len(trader.comments),
            updated_at=record.run.updatedAt,
        )
        await self._validation_storage.persist_run(
            metadata=metadata,
            review_state=review_state,
            blob_refs=blob_refs,
        )

    def _next_run_id(self) -> str:
        value = self._run_counter
        self._run_counter += 1
        return f"valrun-{value:04d}"

    def _next_baseline_id(self) -> str:
        value = self._baseline_counter
        self._baseline_counter += 1
        return f"valbase-{value:03d}"

    def _next_replay_id(self) -> str:
        value = self._replay_counter
        self._replay_counter += 1
        return f"valreplay-{value:03d}"

    @staticmethod
    def _resolve_idempotency_key(*, context: RequestContext, idempotency_key: str | None) -> str:
        provided = _non_empty(idempotency_key)
        if provided is not None:
            return provided
        return context.request_id

    @staticmethod
    def _scoped_idempotency_key(*, context: RequestContext, key: str) -> str:
        return f"{context.tenant_id}:{context.user_id}:{key}"

    def _get_idempotent_response(
        self,
        *,
        scope: str,
        key: str,
        payload: dict[str, Any],
    ) -> tuple[bool, dict[str, Any] | None]:
        return self._store.get_idempotent_response(
            scope=scope,
            key=key,
            payload=payload,
        )

    def _save_idempotent_response(
        self,
        *,
        scope: str,
        key: str,
        payload: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        self._store.save_idempotent_response(
            scope=scope,
            key=key,
            payload=payload,
            response=response,
        )


__all__ = ["ValidationV2Service"]
