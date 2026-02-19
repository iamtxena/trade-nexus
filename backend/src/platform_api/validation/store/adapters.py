"""Store adapters for portable validation module boundaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from src.platform_api.validation.store.metadata import (
    ValidationDecision,
    ValidationProfile,
    ValidationReviewStateMetadata,
    ValidationRunDecision,
    ValidationRunMetadata,
    ValidationStorageService,
    ValidationTraderReviewStatus,
)
from src.platform_api.validation.store.ports import ValidationStorePort, ValidationStoreRecord


def _string_value(value: object, *, fallback: str) -> str:
    if isinstance(value, str) and value.strip() != "":
        return value
    return fallback


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _len_of_sequence(value: object) -> int:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return len(value)
    return 0


class ValidationStorageServiceAdapter(ValidationStorePort):
    """Adapter that persists portable records via ValidationStorageService."""

    def __init__(self, service: ValidationStorageService) -> None:
        self._service = service

    async def persist(self, record: ValidationStoreRecord) -> None:
        trader_review = _mapping(_mapping(record.artifact).get("traderReview"))

        profile = _string_value(record.profile, fallback="STANDARD")
        if profile not in {"FAST", "STANDARD", "EXPERT"}:
            profile = "STANDARD"

        final_decision = _string_value(record.final_decision, fallback="fail")
        if final_decision not in {"pending", "pass", "conditional_pass", "fail"}:
            final_decision = "fail"

        trader_status = _string_value(trader_review.get("status"), fallback="not_requested")
        if trader_status not in {"not_requested", "requested", "approved", "rejected"}:
            trader_status = "not_requested"

        agent_status = _string_value(record.agent_review.get("status"), fallback="fail")
        if agent_status not in {"pass", "conditional_pass", "fail"}:
            agent_status = "fail"

        metadata = ValidationRunMetadata(
            run_id=record.run_id,
            request_id=record.request_id,
            tenant_id=record.tenant_id,
            user_id=record.user_id,
            profile=cast(ValidationProfile, profile),
            status="completed",
            final_decision=cast(ValidationRunDecision, final_decision),
            artifact_ref=record.artifact_ref,
            artifact_schema_version=_string_value(
                _mapping(record.artifact).get("schemaVersion"),
                fallback="validation-run.v1",
            ),
            updated_at=record.created_at,
            created_at=record.created_at,
        )
        review_state = ValidationReviewStateMetadata(
            run_id=record.run_id,
            agent_status=cast(ValidationDecision, agent_status),
            agent_summary=_string_value(
                record.agent_review.get("summary"),
                fallback="Agent review summary unavailable.",
            ),
            findings_count=_len_of_sequence(record.agent_review.get("findings")),
            trader_required=bool(trader_review.get("required", False)),
            trader_status=cast(ValidationTraderReviewStatus, trader_status),
            comments_count=_len_of_sequence(trader_review.get("comments")),
            updated_at=record.created_at,
        )

        await self._service.persist_run(
            metadata=metadata,
            review_state=review_state,
            blob_refs=(),
        )


__all__ = ["ValidationStorageServiceAdapter"]
