"""Services backing frozen /v2/validation-* runtime handlers."""

from __future__ import annotations

import copy
import html
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
    CreateValidationReviewCommentRequest,
    CreateValidationReviewDecisionRequest,
    CreateValidationReviewRenderRequest,
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
    ValidationReviewArtifact,
    ValidationReviewComment,
    ValidationReviewCommentResponse,
    ValidationReviewDecision,
    ValidationReviewDecisionResponse,
    ValidationReviewRenderJob,
    ValidationReviewRenderResponse,
    ValidationReviewRunDetailResponse,
    ValidationReviewRunListResponse,
    ValidationReviewRunSummary,
    ValidationRun,
    ValidationRunActorMetadata,
    ValidationRunArtifact,
    ValidationRunListResponse,
    ValidationRunResponse,
    ValidationRunReviewResponse,
)
from src.platform_api.services.validation_agent_review_service import ValidationAgentReviewService
from src.platform_api.services.validation_deterministic_service import (
    DeterministicValidationEngine,
    DeterministicValidationEvidence,
    ValidationArtifactContext,
    ValidationPolicyConfig,
)
from src.platform_api.services.validation_identity_service import (
    SharedValidationInviteRecord,
    SharePermission,
    ValidationIdentityService,
)
from src.platform_api.services.validation_replay_policy import (
    ValidationReplayInputs,
    evaluate_replay_policy,
)
from src.platform_api.state_store import InMemoryStateStore, utc_now
from src.platform_api.validation.render import InMemoryValidationRenderer, ValidationRenderPort
from src.platform_api.validation.storage import (
    InMemoryValidationMetadataStore,
    ValidationBaselineMetadata,
    ValidationBlobReferenceMetadata,
    ValidationReplayMetadata,
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
    owner_user_id: str
    actor_type: Literal["user", "bot"]
    actor_id: str
    run: ValidationRun
    artifact: ValidationRunArtifact
    llm_snapshot: ValidationLlmSnapshotArtifact
    policy: ValidationPolicyConfig
    trader_decision: ValidationDecision | None = None
    render_jobs: dict[str, ValidationRenderJob] = field(default_factory=dict)
    render_audit_blobs: dict[str, _ValidationRenderBlob] = field(default_factory=dict)
    review_comments: list[ValidationReviewComment] = field(default_factory=list)
    review_decision: ValidationReviewDecision | None = None
    review_render_jobs: dict[str, ValidationReviewRenderJob] = field(default_factory=dict)


@dataclass(frozen=True)
class _ValidationRenderBlob:
    ref: str
    content_type: str
    payload: bytes


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
        identity_service: ValidationIdentityService,
        validation_storage: ValidationStorageService | None = None,
        renderer: ValidationRenderPort | None = None,
        deterministic_engine: DeterministicValidationEngine | None = None,
        agent_review_service: ValidationAgentReviewService | None = None,
    ) -> None:
        self._store = store
        self._identity_service = identity_service
        self._validation_storage = validation_storage or ValidationStorageService(
            metadata_store=InMemoryValidationMetadataStore()
        )
        self._renderer = renderer or InMemoryValidationRenderer()
        self._deterministic_engine = deterministic_engine or DeterministicValidationEngine()
        self._agent_review_service = agent_review_service or ValidationAgentReviewService()

        self._runs: dict[str, _ValidationRunRecord] = {}
        self._baselines: dict[str, _ValidationBaselineRecord] = {}
        self._replays: dict[str, ValidationRegressionReplay] = {}
        self._run_counter = 1
        self._baseline_counter = 1
        self._replay_counter = 1
        self._review_comment_counter = 1

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
            user_id=context.owner_user_id or context.user_id,
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
            "budget": agent_result.budget.to_contract_payload(),
        }

        trader_status = "requested" if policy.require_trader_review else "not_requested"
        final_decision = self._resolve_final_decision(
            deterministic_decision=deterministic_result.final_decision,
            agent_status=agent_result.status,
            trader_status=trader_status,
            policy=policy,
        )
        actor_metadata = ValidationRunActorMetadata(
            actorType=cast(Literal["user", "bot"], context.actor_type),
            actorId=context.actor_id or context.user_id,
            userId=(context.owner_user_id or context.user_id) if context.actor_type == "user" else None,
            botId=(context.actor_id or context.user_id) if context.actor_type == "bot" else None,
            metadata={"ownerUserId": context.owner_user_id or context.user_id},
        )
        artifact_payload["traderReview"] = {
            "required": policy.require_trader_review,
            "status": trader_status,
            "comments": [],
        }
        artifact_payload["actor"] = actor_metadata.model_dump(mode="json")
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
            actor=actor_metadata,
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
            owner_user_id=context.owner_user_id or context.user_id,
            actor_type=cast(Literal["user", "bot"], context.actor_type),
            actor_id=context.actor_id or context.user_id,
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

    async def list_validation_runs(self, *, context: RequestContext) -> ValidationRunListResponse:
        runs = [
            record.run.model_copy()
            for record in self._runs.values()
            if record.tenant_id == context.tenant_id and record.owner_user_id == context.user_id
        ]
        runs.sort(key=lambda run: run.updatedAt, reverse=True)
        return ValidationRunListResponse(
            requestId=context.request_id,
            runs=runs,
        )

    async def get_validation_run(self, *, run_id: str, context: RequestContext) -> ValidationRunResponse:
        record = self._require_run(run_id=run_id, context=context)
        return ValidationRunResponse(requestId=context.request_id, run=record.run)

    async def get_shared_validation_run(self, *, run_id: str, context: RequestContext) -> ValidationRunResponse:
        record = self._require_shared_run(run_id=run_id, context=context, required_permission="view")
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

    async def get_shared_validation_run_artifact(
        self,
        *,
        run_id: str,
        context: RequestContext,
    ) -> ValidationArtifactResponse:
        record = self._require_shared_run(run_id=run_id, context=context, required_permission="view")
        return ValidationArtifactResponse(
            requestId=context.request_id,
            artifactType="validation_run",
            artifact=record.artifact,
        )

    async def list_validation_review_runs(
        self,
        *,
        context: RequestContext,
        status_filter: str | None = None,
        final_decision_filter: str | None = None,
        cursor: str | None = None,
        limit: int = 25,
    ) -> ValidationReviewRunListResponse:
        items = [
            self._build_validation_review_run_summary(record=record)
            for record in self._runs.values()
            if record.tenant_id == context.tenant_id and record.owner_user_id == context.user_id
        ]
        if status_filter is not None:
            items = [item for item in items if item.status == status_filter]
        if final_decision_filter is not None:
            items = [item for item in items if item.finalDecision == final_decision_filter]
        items.sort(key=lambda item: item.updatedAt, reverse=True)

        start = self._decode_pagination_cursor(cursor=cursor)
        bounded_start = min(start, len(items))
        page = items[bounded_start : bounded_start + limit]
        next_cursor: str | None = None
        if bounded_start + limit < len(items):
            next_cursor = str(bounded_start + limit)
        return ValidationReviewRunListResponse(
            requestId=context.request_id,
            items=page,
            nextCursor=next_cursor,
        )

    async def get_validation_review_run(
        self,
        *,
        run_id: str,
        context: RequestContext,
    ) -> ValidationReviewRunDetailResponse:
        record = self._require_run(run_id=run_id, context=context)
        review_artifact = ValidationReviewArtifact(
            schemaVersion="validation-review.v1",
            run=record.run.model_copy(),
            artifact=record.artifact.model_copy(),
            comments=[item.model_copy() for item in record.review_comments],
            decision=record.review_decision.model_copy() if record.review_decision is not None else None,
            renders=[
                item.model_copy()
                for item in sorted(
                    record.review_render_jobs.values(),
                    key=lambda render_job: render_job.requestedAt,
                )
            ],
        )
        return ValidationReviewRunDetailResponse(
            requestId=context.request_id,
            artifact=review_artifact,
        )

    async def create_validation_review_comment(
        self,
        *,
        run_id: str,
        request: CreateValidationReviewCommentRequest,
        context: RequestContext,
        idempotency_key: str | None,
    ) -> ValidationReviewCommentResponse:
        payload = {"runId": run_id, **request.model_dump(mode="json")}
        key = self._resolve_idempotency_key(context=context, idempotency_key=idempotency_key)
        conflict, cached = self._get_idempotent_response(
            scope="validation_review_comments",
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
            return ValidationReviewCommentResponse.model_validate(cached)

        record = self._require_run(run_id=run_id, context=context)
        normalized_body = _non_empty(request.body)
        if normalized_body is None:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_REVIEW_INVALID",
                message="body must be a non-empty string.",
                request_id=context.request_id,
                details={"body": request.body},
            )
        evidence_refs = self._normalize_evidence_refs(
            evidence_refs=request.evidenceRefs,
            request_id=context.request_id,
        )

        created_at = utc_now()
        comment = ValidationReviewComment(
            id=self._next_review_comment_id(),
            runId=run_id,
            tenantId=context.tenant_id,
            userId=context.user_id,
            body=normalized_body,
            evidenceRefs=evidence_refs,
            createdAt=created_at,
        )
        record.review_comments.append(comment)
        await self._touch_run_record(record=record, updated_at=created_at)

        response = ValidationReviewCommentResponse(
            requestId=context.request_id,
            runId=run_id,
            commentAccepted=True,
            comment=comment,
        )
        self._save_idempotent_response(
            scope="validation_review_comments",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
            response=response.model_dump(mode="json"),
        )
        return response

    async def create_validation_review_decision(
        self,
        *,
        run_id: str,
        request: CreateValidationReviewDecisionRequest,
        context: RequestContext,
        idempotency_key: str | None,
    ) -> ValidationReviewDecisionResponse:
        payload = {"runId": run_id, **request.model_dump(mode="json")}
        key = self._resolve_idempotency_key(context=context, idempotency_key=idempotency_key)
        conflict, cached = self._get_idempotent_response(
            scope="validation_review_decisions",
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
            return ValidationReviewDecisionResponse.model_validate(cached)

        record = self._require_run(run_id=run_id, context=context)
        if request.action == "approve" and request.decision == "fail":
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_REVIEW_INVALID",
                message="action=approve cannot be used with decision=fail.",
                request_id=context.request_id,
                details={"action": request.action, "decision": request.decision},
            )
        if request.action == "reject" and request.decision != "fail":
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_REVIEW_INVALID",
                message="action=reject requires decision=fail.",
                request_id=context.request_id,
                details={"action": request.action, "decision": request.decision},
            )
        normalized_reason = _non_empty(request.reason)
        if normalized_reason is None:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_REVIEW_INVALID",
                message="reason must be a non-empty string.",
                request_id=context.request_id,
                details={"reason": request.reason},
            )
        evidence_refs = self._normalize_evidence_refs(
            evidence_refs=request.evidenceRefs,
            request_id=context.request_id,
        )

        created_at = utc_now()
        decision = ValidationReviewDecision(
            runId=run_id,
            action=request.action,
            decision=request.decision,
            reason=normalized_reason,
            evidenceRefs=evidence_refs,
            decidedByTenantId=context.tenant_id,
            decidedByUserId=context.user_id,
            createdAt=created_at,
        )
        record.review_decision = decision

        artifact_payload = record.artifact.model_dump(mode="json")
        snapshot_payload = record.llm_snapshot.model_dump(mode="json")
        trader_review = cast(dict[str, Any], artifact_payload["traderReview"])
        trader_review["status"] = "approved" if request.action == "approve" else "rejected"
        record.trader_decision = cast(ValidationDecision, request.decision)
        deterministic_decision = self._resolve_deterministic_decision(artifact_payload)
        agent_review_payload = cast(dict[str, Any], artifact_payload["agentReview"])
        final_decision = self._resolve_final_decision(
            deterministic_decision=deterministic_decision,
            agent_status=cast(ValidationDecision, agent_review_payload["status"]),
            trader_status=cast(str, trader_review["status"]),
            policy=record.policy,
            trader_decision=record.trader_decision,
        )
        artifact_payload["finalDecision"] = final_decision
        snapshot_payload["finalDecision"] = final_decision

        record.artifact = ValidationRunArtifact.model_validate(artifact_payload)
        record.llm_snapshot = ValidationLlmSnapshotArtifact.model_validate(snapshot_payload)
        await self._touch_run_record(
            record=record,
            updated_at=created_at,
            final_decision=final_decision,
        )

        response = ValidationReviewDecisionResponse(
            requestId=context.request_id,
            runId=run_id,
            decisionAccepted=True,
            decision=decision,
        )
        self._save_idempotent_response(
            scope="validation_review_decisions",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
            response=response.model_dump(mode="json"),
        )
        return response

    async def create_validation_review_render(
        self,
        *,
        run_id: str,
        request: CreateValidationReviewRenderRequest,
        context: RequestContext,
        idempotency_key: str | None,
    ) -> ValidationReviewRenderResponse:
        payload = {"runId": run_id, **request.model_dump(mode="json")}
        key = self._resolve_idempotency_key(context=context, idempotency_key=idempotency_key)
        conflict, cached = self._get_idempotent_response(
            scope="validation_review_renders",
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
            return ValidationReviewRenderResponse.model_validate(cached)

        record = self._require_run(run_id=run_id, context=context)
        render_job = record.review_render_jobs.get(request.format)
        if render_job is None:
            now = utc_now()
            render_job = ValidationReviewRenderJob(
                runId=run_id,
                format=request.format,
                status="queued",
                artifactRef=None,
                downloadUrl=None,
                checksumSha256=None,
                expiresAt=None,
                requestedAt=now,
                updatedAt=now,
            )
            record.review_render_jobs[request.format] = render_job
            await self._touch_run_record(record=record, updated_at=now)

        response = ValidationReviewRenderResponse(
            requestId=context.request_id,
            render=render_job,
        )
        self._save_idempotent_response(
            scope="validation_review_renders",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
            response=response.model_dump(mode="json"),
        )
        return response

    async def get_validation_review_render(
        self,
        *,
        run_id: str,
        format: Literal["html", "pdf"],
        context: RequestContext,
    ) -> ValidationReviewRenderResponse:
        record = self._require_run(run_id=run_id, context=context)
        render_job = record.review_render_jobs.get(format)
        if render_job is None:
            raise PlatformAPIError(
                status_code=404,
                code="VALIDATION_RENDER_NOT_FOUND",
                message=f"Validation review render {format} not found for run {run_id}.",
                request_id=context.request_id,
            )
        return ValidationReviewRenderResponse(
            requestId=context.request_id,
            render=render_job,
        )

    async def create_validation_run_invite(
        self,
        *,
        run_id: str,
        invitee_email: str,
        permission: SharePermission,
        expires_at: str | None,
        context: RequestContext,
    ) -> SharedValidationInviteRecord:
        record = self._require_run(run_id=run_id, context=context)
        return self._identity_service.create_run_share_invite(
            context=context,
            run_id=record.run.id,
            owner_user_id=record.owner_user_id,
            invitee_email=invitee_email,
            permission=permission,
            expires_at=expires_at,
        )

    async def list_validation_run_invites(
        self,
        *,
        run_id: str,
        context: RequestContext,
    ) -> list[SharedValidationInviteRecord]:
        record = self._require_run(run_id=run_id, context=context)
        return self._identity_service.list_run_share_invites(
            context=context,
            run_id=record.run.id,
            owner_user_id=record.owner_user_id,
        )

    async def revoke_validation_invite(
        self,
        *,
        invite_id: str,
        context: RequestContext,
    ) -> SharedValidationInviteRecord:
        return self._identity_service.revoke_run_share_invite(
            context=context,
            invite_id=invite_id,
        )

    async def accept_validation_invite_on_login(
        self,
        *,
        invite_id: str,
        accepted_email: str,
        context: RequestContext,
    ) -> SharedValidationInviteRecord:
        return self._identity_service.accept_run_share_invite(
            context=context,
            invite_id=invite_id,
            accepted_email=accepted_email,
        )

    async def submit_validation_run_review(
        self,
        *,
        run_id: str,
        request: CreateValidationRunReviewRequest,
        context: RequestContext,
        idempotency_key: str | None,
    ) -> ValidationRunReviewResponse:
        return await self._submit_validation_run_review(
            run_id=run_id,
            request=request,
            context=context,
            idempotency_key=idempotency_key,
            shared_surface=False,
        )

    async def submit_shared_validation_run_review(
        self,
        *,
        run_id: str,
        request: CreateValidationRunReviewRequest,
        context: RequestContext,
        idempotency_key: str | None,
    ) -> ValidationRunReviewResponse:
        return await self._submit_validation_run_review(
            run_id=run_id,
            request=request,
            context=context,
            idempotency_key=idempotency_key,
            shared_surface=True,
        )

    async def _submit_validation_run_review(
        self,
        *,
        run_id: str,
        request: CreateValidationRunReviewRequest,
        context: RequestContext,
        idempotency_key: str | None,
        shared_surface: bool,
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

        if shared_surface:
            record = self._require_shared_run(run_id=run_id, context=context, required_permission="review")
        else:
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
            existing_agent_review = cast(dict[str, Any], artifact_payload["agentReview"])
            artifact_payload["agentReview"] = {
                "status": decision,
                "summary": summary,
                "findings": findings_payload,
                "budget": existing_agent_review.get("budget"),
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
        if reviewer_type == "trader":
            record.trader_decision = cast(ValidationDecision, decision)
        final_decision = self._resolve_final_decision(
            deterministic_decision=deterministic_decision,
            agent_status=cast(ValidationDecision, agent_review_payload["status"]),
            trader_status=trader_status,
            policy=record.policy,
            trader_decision=record.trader_decision,
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
        format_name = cast(Literal["html", "pdf"], requested_format)

        record = self._require_run(run_id=run_id, context=context)
        render_job, audit_blob = self._execute_optional_render(
            run_id=run_id,
            output_format=format_name,
            record=record,
            context=context,
        )
        record.render_jobs[format_name] = render_job
        record.render_audit_blobs[format_name] = audit_blob
        try:
            await self._persist_run_metadata(record=record)
        except Exception:
            logger.warning(
                "Validation render metadata persistence failed for run %s format %s.",
                run_id,
                format_name,
                exc_info=True,
            )
            log_context_event(
                logger,
                level=logging.WARNING,
                message="Validation render metadata persistence failed.",
                context=context,
                component="validation",
                operation="create_validation_render",
                resource_type="validation_run",
                resource_id=run_id,
                renderFormat=format_name,
                renderStatus=render_job.status,
            )

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
        if (
            run_record is None
            or run_record.tenant_id != context.tenant_id
            or run_record.owner_user_id != context.user_id
        ):
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
        if (
            candidate is None
            or candidate.tenant_id != context.tenant_id
            or candidate.owner_user_id != context.user_id
        ):
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

        if baseline_run.run.status != "completed" or candidate.run.status != "completed":
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_STATE_INVALID",
                message="Baseline and candidate runs must both be completed for replay.",
                request_id=context.request_id,
                details={
                    "baselineRunStatus": baseline_run.run.status,
                    "candidateRunStatus": candidate.run.status,
                },
            )

        baseline_strategy_id = baseline_run.artifact.strategyRef.strategyId
        candidate_strategy_id = candidate.artifact.strategyRef.strategyId
        if baseline_strategy_id != candidate_strategy_id:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_STATE_INVALID",
                message="Validation replay requires baseline and candidate runs from the same strategyId.",
                request_id=context.request_id,
                details={
                    "baselineStrategyId": baseline_strategy_id,
                    "candidateStrategyId": candidate_strategy_id,
                },
            )

        baseline_decision = cast(ValidationDecision, baseline_run.run.finalDecision)
        candidate_decision = cast(ValidationDecision, candidate.run.finalDecision)
        baseline_metric_drift_pct = baseline_run.artifact.deterministicChecks.metricConsistency.driftPct
        candidate_metric_drift_pct = candidate.artifact.deterministicChecks.metricConsistency.driftPct
        metric_threshold_pct = min(
            baseline_run.policy.resolved_metric_tolerance_pct(),
            candidate.policy.resolved_metric_tolerance_pct(),
        )

        replay_outcome = evaluate_replay_policy(
            inputs=ValidationReplayInputs(
                baseline_decision=baseline_decision,
                candidate_decision=candidate_decision,
                baseline_metric_drift_pct=baseline_metric_drift_pct,
                candidate_metric_drift_pct=candidate_metric_drift_pct,
                metric_drift_threshold_pct=metric_threshold_pct,
                block_merge_on_fail=candidate.policy.block_merge_on_fail,
                block_release_on_fail=candidate.policy.block_release_on_fail,
                block_merge_on_agent_fail=candidate.policy.block_merge_on_agent_fail,
                block_release_on_agent_fail=candidate.policy.block_release_on_agent_fail,
            )
        )
        decision: ValidationReplayDecision = replay_outcome.decision

        replay_id = self._next_replay_id()
        if replay_outcome.reasons:
            summary = "Replay comparison detected regression signals."
        else:
            summary = "Replay comparison passed without regression."
        replay = ValidationRegressionReplay(
            id=replay_id,
            baselineId=request.baselineId,
            candidateRunId=request.candidateRunId,
            status="completed",
            decision=decision,
            mergeBlocked=replay_outcome.merge_blocked,
            releaseBlocked=replay_outcome.release_blocked,
            mergeGateStatus=replay_outcome.merge_gate_status,
            releaseGateStatus=replay_outcome.release_gate_status,
            baselineDecision=replay_outcome.baseline_decision,
            candidateDecision=replay_outcome.candidate_decision,
            metricDriftDeltaPct=round(replay_outcome.metric_drift_delta_pct, 6),
            metricDriftThresholdPct=round(replay_outcome.metric_drift_threshold_pct, 6),
            thresholdBreached=replay_outcome.threshold_breached,
            reasons=list(replay_outcome.reasons),
            summary=summary,
        )
        self._replays[replay_id] = replay
        await self._persist_replay_metadata(
            replay=replay,
            baseline_run_id=baseline.baseline.runId,
            context=context,
        )

        response = ValidationRegressionReplayResponse(requestId=context.request_id, replay=replay)
        self._save_idempotent_response(
            scope="validation_replays",
            key=self._scoped_idempotency_key(context=context, key=key),
            payload=payload,
            response=response.model_dump(mode="json"),
        )
        return response

    def _execute_optional_render(
        self,
        *,
        run_id: str,
        output_format: Literal["html", "pdf"],
        record: _ValidationRunRecord,
        context: RequestContext,
    ) -> tuple[ValidationRenderJob, _ValidationRenderBlob]:
        artifact_payload = record.artifact.model_dump(mode="json")
        try:
            rendered_artifact = self._renderer.render(
                artifact=artifact_payload,
                output_format=output_format,
            )
            if rendered_artifact is None:
                raise RuntimeError("Validation renderer returned no artifact output.")
            if rendered_artifact.output_format != output_format:
                raise RuntimeError(
                    "Validation renderer output format mismatch: "
                    f"expected {output_format}, got {rendered_artifact.output_format}."
                )
            render_ref = rendered_artifact.ref.strip()
            if not is_valid_blob_reference(render_ref):
                raise RuntimeError(
                    "Validation renderer produced an invalid blob reference for audit persistence."
                )

            success_blob = self._build_success_render_blob(
                run_id=run_id,
                output_format=output_format,
                render_ref=render_ref,
                artifact_payload=artifact_payload,
            )
            render_job = ValidationRenderJob(
                runId=run_id,
                format=output_format,
                status="completed",
                artifactRef=success_blob.ref,
            )
            log_context_event(
                logger,
                level=logging.INFO,
                message="Validation render completed.",
                context=context,
                component="validation",
                operation="create_validation_render",
                resource_type="validation_run",
                resource_id=run_id,
                renderFormat=output_format,
                renderStatus=render_job.status,
            )
            return render_job, success_blob
        except Exception as exc:
            failure_blob = self._build_failure_render_blob(
                run_id=run_id,
                output_format=output_format,
                error_message=str(exc),
            )
            render_job = ValidationRenderJob(
                runId=run_id,
                format=output_format,
                status="failed",
                artifactRef=failure_blob.ref,
            )
            logger.warning(
                "Validation render failed for run %s format %s.",
                run_id,
                output_format,
                exc_info=True,
            )
            log_context_event(
                logger,
                level=logging.WARNING,
                message="Validation render failed.",
                context=context,
                component="validation",
                operation="create_validation_render",
                resource_type="validation_run",
                resource_id=run_id,
                renderFormat=output_format,
                renderStatus=render_job.status,
                errorType=type(exc).__name__,
                errorMessage=_non_empty(str(exc)) or type(exc).__name__,
            )
            return render_job, failure_blob

    def _build_success_render_blob(
        self,
        *,
        run_id: str,
        output_format: Literal["html", "pdf"],
        render_ref: str,
        artifact_payload: dict[str, Any],
    ) -> _ValidationRenderBlob:
        if output_format == "html":
            return _ValidationRenderBlob(
                ref=render_ref,
                content_type="text/html; charset=utf-8",
                payload=self._build_html_render_payload(
                    run_id=run_id,
                    artifact_payload=artifact_payload,
                ),
            )
        return _ValidationRenderBlob(
            ref=render_ref,
            content_type="application/pdf",
            payload=self._build_pdf_render_payload(
                run_id=run_id,
                artifact_payload=artifact_payload,
            ),
        )

    def _build_failure_render_blob(
        self,
        *,
        run_id: str,
        output_format: Literal["html", "pdf"],
        error_message: str,
    ) -> _ValidationRenderBlob:
        failure_ref = f"blob://validation/{run_id}/render-{output_format}-failure.json"
        failure_payload = {
            "runId": run_id,
            "format": output_format,
            "status": "failed",
            "failedAt": utc_now(),
            "error": {
                "code": "VALIDATION_RENDER_EXECUTION_FAILED",
                "message": _non_empty(error_message) or "Validation render failed.",
            },
        }
        return _ValidationRenderBlob(
            ref=failure_ref,
            content_type="application/json",
            payload=json.dumps(failure_payload, sort_keys=True).encode("utf-8"),
        )

    @staticmethod
    def _build_html_render_payload(*, run_id: str, artifact_payload: dict[str, Any]) -> bytes:
        artifact_json = json.dumps(artifact_payload, sort_keys=True, indent=2)
        escaped_json = html.escape(artifact_json)
        final_decision = html.escape(str(artifact_payload.get("finalDecision", "unknown")))
        html_payload = (
            "<!doctype html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <meta charset=\"utf-8\" />\n"
            f"  <title>Validation Report {html.escape(run_id)}</title>\n"
            "</head>\n"
            "<body>\n"
            f"  <h1>Validation Report {html.escape(run_id)}</h1>\n"
            f"  <p>Final decision: {final_decision}</p>\n"
            "  <pre>\n"
            f"{escaped_json}\n"
            "  </pre>\n"
            "</body>\n"
            "</html>\n"
        )
        return html_payload.encode("utf-8")

    @staticmethod
    def _build_pdf_render_payload(*, run_id: str, artifact_payload: dict[str, Any]) -> bytes:
        decision = str(artifact_payload.get("finalDecision", "unknown"))
        policy_payload = artifact_payload.get("policy")
        profile = "unknown"
        if isinstance(policy_payload, dict):
            profile = str(policy_payload.get("profile", "unknown"))
        lines = [
            f"Validation Report: {run_id}",
            f"Final Decision: {decision}",
            f"Policy Profile: {profile}",
        ]
        line_commands: list[str] = []
        for line in lines:
            escaped_line = ValidationV2Service._escape_pdf_text(line)
            line_commands.append(f"({escaped_line}) Tj")
            line_commands.append("0 -16 Td")
        content_stream = "BT\n/F1 12 Tf\n72 720 Td\n" + "\n".join(line_commands) + "\nET"
        content_payload = content_stream.encode("utf-8")

        objects: list[bytes] = [
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
            (
                b"3 0 obj\n"
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\n"
                b"endobj\n"
            ),
            b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
            (
                f"5 0 obj\n<< /Length {len(content_payload)} >>\nstream\n".encode("ascii")
                + content_payload
                + b"\nendstream\nendobj\n"
            ),
        ]

        header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        parts: list[bytes] = [header]
        offsets: list[int] = []
        cursor = len(header)
        for item in objects:
            offsets.append(cursor)
            parts.append(item)
            cursor += len(item)

        xref_start = cursor
        xref_rows = [b"0000000000 65535 f \n"]
        for offset in offsets:
            xref_rows.append(f"{offset:010d} 00000 n \n".encode("ascii"))
        xref = b"xref\n0 6\n" + b"".join(xref_rows)
        trailer = (
            b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
            + str(xref_start).encode("ascii")
            + b"\n%%EOF\n"
        )
        parts.append(xref)
        parts.append(trailer)
        return b"".join(parts)

    @staticmethod
    def _escape_pdf_text(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    @staticmethod
    def _render_blob_kind(*, output_format: Literal["html", "pdf"]) -> Literal["render_html", "render_pdf"]:
        return "render_html" if output_format == "html" else "render_pdf"

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
        if (
            record is None
            or record.tenant_id != context.tenant_id
            or record.owner_user_id != context.user_id
        ):
            raise PlatformAPIError(
                status_code=404,
                code="VALIDATION_RUN_NOT_FOUND",
                message=f"Validation run {run_id} not found.",
                request_id=context.request_id,
            )
        return record

    def _require_shared_run(
        self,
        *,
        run_id: str,
        context: RequestContext,
        required_permission: SharePermission,
    ) -> _ValidationRunRecord:
        record = self._runs.get(run_id)
        if record is None or record.tenant_id != context.tenant_id:
            raise PlatformAPIError(
                status_code=404,
                code="VALIDATION_RUN_NOT_FOUND",
                message=f"Validation run {run_id} not found.",
                request_id=context.request_id,
            )

        if not self._identity_service.can_access_run(
            run_id=run_id,
            owner_user_id=record.owner_user_id,
            user_id=context.user_id,
            required_permission=required_permission,
        ):
            raise PlatformAPIError(
                status_code=403,
                code="VALIDATION_RUN_ACCESS_DENIED",
                message=f"Validation run {run_id} access denied.",
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
        ).encode()
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
            b"created ord-001\n"
            b"accepted ord-001\n"
            b"filled ord-001\n"
        )
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
        for output_format, render_blob in sorted(record.render_audit_blobs.items()):
            if output_format not in {"html", "pdf"}:
                continue
            normalized_format = cast(Literal["html", "pdf"], output_format)
            blob_refs.append(
                ValidationBlobReferenceMetadata.from_payload(
                    run_id=run_id,
                    kind=self._render_blob_kind(output_format=normalized_format),
                    ref=render_blob.ref,
                    payload=render_blob.payload,
                    content_type=render_blob.content_type,
                )
            )

        review = artifact.agentReview
        trader = artifact.traderReview
        metadata = ValidationRunMetadata(
            run_id=run_id,
            request_id=artifact.requestId,
            tenant_id=artifact.tenantId,
            user_id=artifact.userId,
            owner_user_id=record.owner_user_id,
            actor_type=record.actor_type,
            actor_id=record.actor_id,
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

    async def _persist_replay_metadata(
        self,
        *,
        replay: ValidationRegressionReplay,
        baseline_run_id: str,
        context: RequestContext,
    ) -> None:
        await self._validation_storage.persist_replay(
            ValidationReplayMetadata(
                replay_id=replay.id,
                baseline_id=replay.baselineId,
                baseline_run_id=baseline_run_id,
                candidate_run_id=replay.candidateRunId,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                decision=cast(Literal["pass", "conditional_pass", "fail", "unknown"], replay.decision),
                merge_blocked=replay.mergeBlocked,
                release_blocked=replay.releaseBlocked,
                merge_gate_status=cast(Literal["pass", "blocked"], replay.mergeGateStatus),
                release_gate_status=cast(Literal["pass", "blocked"], replay.releaseGateStatus),
                baseline_decision=cast(ValidationDecision, replay.baselineDecision),
                candidate_decision=cast(ValidationDecision, replay.candidateDecision),
                metric_drift_delta_pct=replay.metricDriftDeltaPct,
                metric_drift_threshold_pct=replay.metricDriftThresholdPct,
                threshold_breached=replay.thresholdBreached,
                reasons=tuple(replay.reasons),
                summary=replay.summary,
            )
        )

    async def _touch_run_record(
        self,
        *,
        record: _ValidationRunRecord,
        updated_at: str,
        final_decision: ValidationDecision | None = None,
    ) -> None:
        updates: dict[str, Any] = {"updatedAt": updated_at}
        if final_decision is not None:
            updates["finalDecision"] = cast(
                Literal["pending", "pass", "conditional_pass", "fail"],
                final_decision,
            )
        record.run = record.run.model_copy(update=updates)
        await self._persist_run_metadata(record=record)

    @staticmethod
    def _decode_pagination_cursor(*, cursor: str | None) -> int:
        normalized = _non_empty(cursor)
        if normalized is None:
            return 0
        try:
            parsed = int(normalized)
        except ValueError:
            return 0
        if parsed < 0:
            return 0
        return parsed

    @staticmethod
    def _normalize_evidence_refs(
        *,
        evidence_refs: list[str],
        request_id: str,
    ) -> list[str]:
        normalized: list[str] = []
        for ref in evidence_refs:
            candidate = _non_empty(ref)
            if candidate is None or not is_valid_blob_reference(candidate):
                raise PlatformAPIError(
                    status_code=400,
                    code="VALIDATION_REVIEW_INVALID",
                    message="evidenceRefs entries must use blob:// reference format.",
                    request_id=request_id,
                    details={"evidenceRef": ref},
                )
            normalized.append(candidate)
        return normalized

    @staticmethod
    def _build_validation_review_run_summary(
        *,
        record: _ValidationRunRecord,
    ) -> ValidationReviewRunSummary:
        trader_status = record.artifact.traderReview.status
        return ValidationReviewRunSummary(
            id=record.run.id,
            status=record.run.status,
            profile=record.run.profile,
            finalDecision=record.run.finalDecision,
            traderReviewStatus=trader_status,
            commentCount=len(record.review_comments),
            pendingDecision=record.review_decision is None and trader_status == "requested",
            createdAt=record.run.createdAt,
            updatedAt=record.run.updatedAt,
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

    def _next_review_comment_id(self) -> str:
        value = self._review_comment_counter
        self._review_comment_counter += 1
        return f"valcomment-{value:03d}"

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
