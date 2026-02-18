"""Validation storage adapters and metadata contracts.

This module provides:
1) metadata models aligned to Supabase tables,
2) blob-reference checksum helpers,
3) a vector-memory hook interface,
4) fail-closed adapter selection for production profile.
"""

from __future__ import annotations

import copy
import hashlib
import inspect
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, cast

from src.platform_api.state_store import utc_now

ValidationProfile = Literal["FAST", "STANDARD", "EXPERT"]
ValidationRunStatus = Literal["queued", "running", "completed", "failed"]
ValidationRunDecision = Literal["pending", "pass", "conditional_pass", "fail"]
ValidationArtifactType = Literal["validation_run", "validation_llm_snapshot"]
ValidationBlobKind = Literal[
    "strategy_code",
    "backtest_report",
    "trades",
    "execution_logs",
    "chart_payload",
    "render_html",
    "render_pdf",
]
ValidationDecision = Literal["pass", "conditional_pass", "fail"]
ValidationTraderReviewStatus = Literal["not_requested", "requested", "approved", "rejected"]

VALIDATION_STORAGE_FAIL_CLOSED_CODE = "VALIDATION_STORAGE_FAIL_CLOSED"

_VALID_PROFILES: set[str] = {"FAST", "STANDARD", "EXPERT"}
_VALID_RUN_STATUSES: set[str] = {"queued", "running", "completed", "failed"}
_VALID_RUN_DECISIONS: set[str] = {"pending", "pass", "conditional_pass", "fail"}
_VALID_ARTIFACT_TYPES: set[str] = {"validation_run", "validation_llm_snapshot"}
_VALID_DECISIONS: set[str] = {"pass", "conditional_pass", "fail"}
_VALID_TRADER_REVIEW_STATUSES: set[str] = {"not_requested", "requested", "approved", "rejected"}
_VALID_BLOB_KINDS: set[str] = {
    "strategy_code",
    "backtest_report",
    "trades",
    "execution_logs",
    "chart_payload",
    "render_html",
    "render_pdf",
}
_PRODUCTION_PROFILE_ALIASES = {"prod", "production", "live"}
_BLOB_REF_PATTERN = re.compile(r"^blob://[A-Za-z0-9._~!$&'()*+,;=:@/-]+$")
_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ValidationMetadataStoreError(RuntimeError):
    """Raised when metadata persistence fails."""


class ValidationStorageFailClosedError(RuntimeError):
    """Raised when production profile cannot resolve required storage adapters."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.code = VALIDATION_STORAGE_FAIL_CLOSED_CODE


def compute_sha256_digest(payload: bytes) -> str:
    """Return lowercase SHA-256 checksum for the payload."""
    return hashlib.sha256(payload).hexdigest()


def is_valid_blob_reference(ref: str) -> bool:
    """Validate canonical blob:// reference format."""
    return bool(_BLOB_REF_PATTERN.fullmatch(ref))


def validate_blob_payload_integrity(reference: ValidationBlobReferenceMetadata, payload: bytes) -> None:
    """Fail when payload checksum does not match stored reference metadata."""
    actual_checksum = compute_sha256_digest(payload)
    if actual_checksum != reference.checksum_sha256:
        raise ValueError(
            "Blob payload checksum mismatch for "
            f"{reference.ref}: expected {reference.checksum_sha256}, got {actual_checksum}."
        )


def _require_non_empty(value: str, *, field_name: str) -> None:
    if value.strip() == "":
        raise ValueError(f"{field_name} must be non-empty.")


def _validate_profile(value: str) -> None:
    if value not in _VALID_PROFILES:
        raise ValueError(f"profile must be one of {sorted(_VALID_PROFILES)}, got {value!r}.")


def _validate_run_status(value: str) -> None:
    if value not in _VALID_RUN_STATUSES:
        raise ValueError(f"status must be one of {sorted(_VALID_RUN_STATUSES)}, got {value!r}.")


def _validate_run_decision(value: str) -> None:
    if value not in _VALID_RUN_DECISIONS:
        raise ValueError(
            f"final_decision must be one of {sorted(_VALID_RUN_DECISIONS)}, got {value!r}."
        )


def _validate_artifact_type(value: str) -> None:
    if value not in _VALID_ARTIFACT_TYPES:
        raise ValueError(f"artifact_type must be one of {sorted(_VALID_ARTIFACT_TYPES)}, got {value!r}.")


def _validate_decision(value: str, *, field_name: str) -> None:
    if value not in _VALID_DECISIONS:
        raise ValueError(f"{field_name} must be one of {sorted(_VALID_DECISIONS)}, got {value!r}.")


def _validate_trader_status(value: str) -> None:
    if value not in _VALID_TRADER_REVIEW_STATUSES:
        raise ValueError(
            f"trader_status must be one of {sorted(_VALID_TRADER_REVIEW_STATUSES)}, got {value!r}."
        )


def _validate_blob_kind(value: str) -> None:
    if value not in _VALID_BLOB_KINDS:
        raise ValueError(f"blob kind must be one of {sorted(_VALID_BLOB_KINDS)}, got {value!r}.")


def _as_int(row: dict[str, Any], key: str) -> int:
    raw = row.get(key)
    if isinstance(raw, bool):
        raise ValidationMetadataStoreError(f"Expected numeric integer for {key}, got bool.")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    raise ValidationMetadataStoreError(f"Expected integer for {key}, got {raw!r}.")


def _as_bool(row: dict[str, Any], key: str) -> bool:
    raw = row.get(key)
    if isinstance(raw, bool):
        return raw
    raise ValidationMetadataStoreError(f"Expected boolean for {key}, got {raw!r}.")


def _as_str(row: dict[str, Any], key: str) -> str:
    raw = row.get(key)
    if isinstance(raw, str) and raw.strip() != "":
        return raw
    raise ValidationMetadataStoreError(f"Expected non-empty string for {key}, got {raw!r}.")


def _as_optional_str(row: dict[str, Any], key: str) -> str | None:
    raw = row.get(key)
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    raise ValidationMetadataStoreError(f"Expected optional string for {key}, got {raw!r}.")


def _is_production_profile(profile: str | None) -> bool:
    if profile is None:
        return False
    return profile.strip().lower() in _PRODUCTION_PROFILE_ALIASES


def _resolve_runtime_profile(runtime_profile: str | None) -> str:
    if isinstance(runtime_profile, str) and runtime_profile.strip() != "":
        return runtime_profile.strip()
    for key in (
        "PLATFORM_RUNTIME_PROFILE",
        "PLATFORM_PROFILE",
        "PLATFORM_ENVIRONMENT",
        "PLATFORM_ENV",
    ):
        value = os.getenv(key)
        if isinstance(value, str) and value.strip() != "":
            return value.strip()
    return "development"


@dataclass(frozen=True)
class ValidationRunMetadata:
    run_id: str
    request_id: str
    tenant_id: str
    user_id: str
    profile: ValidationProfile
    status: ValidationRunStatus
    final_decision: ValidationRunDecision
    artifact_ref: str
    artifact_type: ValidationArtifactType = "validation_run"
    artifact_schema_version: str = "validation-run.v1"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        _require_non_empty(self.run_id, field_name="run_id")
        _require_non_empty(self.request_id, field_name="request_id")
        _require_non_empty(self.tenant_id, field_name="tenant_id")
        _require_non_empty(self.user_id, field_name="user_id")
        _validate_profile(self.profile)
        _validate_run_status(self.status)
        _validate_run_decision(self.final_decision)
        _validate_artifact_type(self.artifact_type)
        _require_non_empty(self.artifact_schema_version, field_name="artifact_schema_version")
        if not is_valid_blob_reference(self.artifact_ref):
            raise ValueError(f"artifact_ref must be a valid blob:// reference, got {self.artifact_ref!r}.")


@dataclass(frozen=True)
class ValidationReviewStateMetadata:
    run_id: str
    agent_status: ValidationDecision
    agent_summary: str
    findings_count: int
    trader_required: bool
    trader_status: ValidationTraderReviewStatus
    comments_count: int = 0
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        _require_non_empty(self.run_id, field_name="run_id")
        _validate_decision(self.agent_status, field_name="agent_status")
        _require_non_empty(self.agent_summary, field_name="agent_summary")
        if self.findings_count < 0:
            raise ValueError("findings_count must be >= 0.")
        if self.comments_count < 0:
            raise ValueError("comments_count must be >= 0.")
        _validate_trader_status(self.trader_status)


@dataclass(frozen=True)
class ValidationBlobReferenceMetadata:
    run_id: str
    kind: ValidationBlobKind
    ref: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        _require_non_empty(self.run_id, field_name="run_id")
        _validate_blob_kind(self.kind)
        if not is_valid_blob_reference(self.ref):
            raise ValueError(f"ref must be a valid blob:// reference, got {self.ref!r}.")
        _require_non_empty(self.content_type, field_name="content_type")
        if self.size_bytes < 0:
            raise ValueError("size_bytes must be >= 0.")
        if not _SHA256_HEX_PATTERN.fullmatch(self.checksum_sha256):
            raise ValueError("checksum_sha256 must be a lowercase 64-char SHA-256 hex digest.")

    @classmethod
    def from_payload(
        cls,
        *,
        run_id: str,
        kind: ValidationBlobKind,
        ref: str,
        payload: bytes,
        content_type: str,
    ) -> ValidationBlobReferenceMetadata:
        return cls(
            run_id=run_id,
            kind=kind,
            ref=ref,
            content_type=content_type,
            size_bytes=len(payload),
            checksum_sha256=compute_sha256_digest(payload),
        )

    def verify_payload(self, payload: bytes) -> bool:
        return compute_sha256_digest(payload) == self.checksum_sha256


@dataclass(frozen=True)
class ValidationBaselineMetadata:
    id: str
    run_id: str
    tenant_id: str
    user_id: str
    name: str
    profile: ValidationProfile
    notes: str | None = None
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        _require_non_empty(self.id, field_name="id")
        _require_non_empty(self.run_id, field_name="run_id")
        _require_non_empty(self.tenant_id, field_name="tenant_id")
        _require_non_empty(self.user_id, field_name="user_id")
        _require_non_empty(self.name, field_name="name")
        _validate_profile(self.profile)


@dataclass(frozen=True)
class PersistedValidationRun:
    metadata: ValidationRunMetadata
    review_state: ValidationReviewStateMetadata | None
    blob_refs: tuple[ValidationBlobReferenceMetadata, ...]


class ValidationVectorHook(Protocol):
    """Extension point for storing review lessons in a vector memory."""

    async def on_validation_run_persisted(
        self,
        *,
        run: ValidationRunMetadata,
        review_state: ValidationReviewStateMetadata | None,
        blob_refs: Sequence[ValidationBlobReferenceMetadata],
    ) -> None:
        ...


class NoopValidationVectorHook:
    """Default vector hook used when no vector integration is configured."""

    async def on_validation_run_persisted(
        self,
        *,
        run: ValidationRunMetadata,
        review_state: ValidationReviewStateMetadata | None,
        blob_refs: Sequence[ValidationBlobReferenceMetadata],
    ) -> None:
        _ = (run, review_state, blob_refs)


class ValidationMetadataStore(Protocol):
    """Persistence contract for validation metadata and baseline indexes."""

    async def upsert_run(
        self,
        *,
        metadata: ValidationRunMetadata,
        review_state: ValidationReviewStateMetadata | None,
        blob_refs: Sequence[ValidationBlobReferenceMetadata],
    ) -> None:
        ...

    async def get_run(self, *, run_id: str, tenant_id: str, user_id: str) -> PersistedValidationRun | None:
        ...

    async def upsert_baseline(self, baseline: ValidationBaselineMetadata) -> None:
        ...

    async def get_baseline(
        self,
        *,
        baseline_id: str,
        tenant_id: str,
        user_id: str,
    ) -> ValidationBaselineMetadata | None:
        ...


class ValidationStorageService:
    """Facade that persists metadata and forwards signals to vector-memory hooks."""

    def __init__(
        self,
        *,
        metadata_store: ValidationMetadataStore,
        vector_hook: ValidationVectorHook | None = None,
    ) -> None:
        self._metadata_store = metadata_store
        self._vector_hook = vector_hook or NoopValidationVectorHook()

    async def persist_run(
        self,
        *,
        metadata: ValidationRunMetadata,
        review_state: ValidationReviewStateMetadata | None,
        blob_refs: Sequence[ValidationBlobReferenceMetadata],
    ) -> None:
        await self._metadata_store.upsert_run(
            metadata=metadata,
            review_state=review_state,
            blob_refs=blob_refs,
        )
        await self._vector_hook.on_validation_run_persisted(
            run=metadata,
            review_state=review_state,
            blob_refs=blob_refs,
        )

    async def get_run(self, *, run_id: str, tenant_id: str, user_id: str) -> PersistedValidationRun | None:
        return await self._metadata_store.get_run(run_id=run_id, tenant_id=tenant_id, user_id=user_id)

    async def persist_baseline(self, baseline: ValidationBaselineMetadata) -> None:
        await self._metadata_store.upsert_baseline(baseline)

    async def get_baseline(
        self,
        *,
        baseline_id: str,
        tenant_id: str,
        user_id: str,
    ) -> ValidationBaselineMetadata | None:
        return await self._metadata_store.get_baseline(
            baseline_id=baseline_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )


class InMemoryValidationMetadataStore:
    """Deterministic in-process persistence used for local/dev validation flows."""

    def __init__(self) -> None:
        self._runs: dict[str, PersistedValidationRun] = {}
        self._baselines: dict[str, ValidationBaselineMetadata] = {}

    async def upsert_run(
        self,
        *,
        metadata: ValidationRunMetadata,
        review_state: ValidationReviewStateMetadata | None,
        blob_refs: Sequence[ValidationBlobReferenceMetadata],
    ) -> None:
        normalized_refs = tuple(sorted(copy.deepcopy(list(blob_refs)), key=lambda item: item.kind))
        self._runs[metadata.run_id] = PersistedValidationRun(
            metadata=copy.deepcopy(metadata),
            review_state=copy.deepcopy(review_state),
            blob_refs=normalized_refs,
        )

    async def get_run(self, *, run_id: str, tenant_id: str, user_id: str) -> PersistedValidationRun | None:
        record = self._runs.get(run_id)
        if record is None:
            return None
        if record.metadata.tenant_id != tenant_id or record.metadata.user_id != user_id:
            return None
        return copy.deepcopy(record)

    async def upsert_baseline(self, baseline: ValidationBaselineMetadata) -> None:
        self._baselines[baseline.id] = copy.deepcopy(baseline)

    async def get_baseline(
        self,
        *,
        baseline_id: str,
        tenant_id: str,
        user_id: str,
    ) -> ValidationBaselineMetadata | None:
        baseline = self._baselines.get(baseline_id)
        if baseline is None:
            return None
        if baseline.tenant_id != tenant_id or baseline.user_id != user_id:
            return None
        return copy.deepcopy(baseline)


class SupabaseValidationMetadataStore:
    """Supabase-backed metadata persistence for validation runs and baselines."""

    def __init__(
        self,
        supabase_client: Any,
        *,
        runs_table: str = "validation_runs",
        review_table: str = "validation_review_states",
        blob_refs_table: str = "validation_blob_refs",
        baselines_table: str = "validation_baselines",
    ) -> None:
        self._client = supabase_client
        self._runs_table = runs_table
        self._review_table = review_table
        self._blob_refs_table = blob_refs_table
        self._baselines_table = baselines_table

    async def upsert_run(
        self,
        *,
        metadata: ValidationRunMetadata,
        review_state: ValidationReviewStateMetadata | None,
        blob_refs: Sequence[ValidationBlobReferenceMetadata],
    ) -> None:
        await self._upsert(
            table=self._runs_table,
            payload=_run_row_from_metadata(metadata),
            on_conflict="run_id",
        )
        if review_state is not None:
            await self._upsert(
                table=self._review_table,
                payload=_review_row_from_metadata(review_state),
                on_conflict="run_id",
            )
        if blob_refs:
            await self._upsert(
                table=self._blob_refs_table,
                payload=[_blob_ref_row_from_metadata(item) for item in blob_refs],
                on_conflict="run_id,kind",
            )

    async def get_run(self, *, run_id: str, tenant_id: str, user_id: str) -> PersistedValidationRun | None:
        run_row = await self._select_one(
            table=self._runs_table,
            filters={
                "run_id": run_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
            },
        )
        if run_row is None:
            return None

        review_row = await self._select_one(
            table=self._review_table,
            filters={"run_id": run_id},
        )
        blob_rows = await self._select_many(
            table=self._blob_refs_table,
            filters={"run_id": run_id},
        )
        blob_refs = tuple(
            sorted(
                (_blob_ref_metadata_from_row(row) for row in blob_rows),
                key=lambda item: item.kind,
            )
        )
        review_state = _review_metadata_from_row(review_row) if review_row is not None else None
        return PersistedValidationRun(
            metadata=_run_metadata_from_row(run_row),
            review_state=review_state,
            blob_refs=blob_refs,
        )

    async def upsert_baseline(self, baseline: ValidationBaselineMetadata) -> None:
        await self._upsert(
            table=self._baselines_table,
            payload=_baseline_row_from_metadata(baseline),
            on_conflict="id",
        )

    async def get_baseline(
        self,
        *,
        baseline_id: str,
        tenant_id: str,
        user_id: str,
    ) -> ValidationBaselineMetadata | None:
        row = await self._select_one(
            table=self._baselines_table,
            filters={
                "id": baseline_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
            },
        )
        if row is None:
            return None
        return _baseline_metadata_from_row(row)

    async def _upsert(self, *, table: str, payload: Any, on_conflict: str) -> None:
        query = self._table(table).upsert(payload, on_conflict=on_conflict)
        await self._execute(query)

    async def _select_one(self, *, table: str, filters: dict[str, object]) -> dict[str, Any] | None:
        rows = await self._select_many(table=table, filters=filters)
        if not rows:
            return None
        return rows[0]

    async def _select_many(self, *, table: str, filters: dict[str, object]) -> list[dict[str, Any]]:
        query = self._table(table).select("*")
        for key, value in filters.items():
            query = query.eq(key, value)
        data = await self._execute(query)
        if data is None:
            return []
        if isinstance(data, dict):
            return [data]
        if not isinstance(data, list):
            raise ValidationMetadataStoreError(
                f"Supabase response for table {table} expected list/dict payload, got {type(data).__name__}."
            )
        rows: list[dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict):
                rows.append(item)
        return rows

    def _table(self, table: str) -> Any:
        if hasattr(self._client, "table"):
            return self._client.table(table)
        if hasattr(self._client, "from_"):
            return self._client.from_(table)
        raise ValidationMetadataStoreError(
            "Supabase client must expose table(name) or from_(name) method."
        )

    async def _execute(self, query: Any) -> Any:
        if not hasattr(query, "execute"):
            raise ValidationMetadataStoreError("Supabase query object does not expose execute().")
        result = query.execute()
        if inspect.isawaitable(result):
            result = await result
        return _extract_supabase_data(result)


def _extract_supabase_data(result: object) -> object:
    if isinstance(result, dict):
        error = result.get("error")
        if error:
            raise ValidationMetadataStoreError(f"Supabase request failed: {error!r}")
        if "data" in result:
            return result["data"]
        return result

    error = getattr(result, "error", None)
    if error:
        raise ValidationMetadataStoreError(f"Supabase request failed: {error!r}")

    if hasattr(result, "data"):
        return getattr(result, "data")
    return result


def _run_row_from_metadata(metadata: ValidationRunMetadata) -> dict[str, object]:
    return {
        "run_id": metadata.run_id,
        "request_id": metadata.request_id,
        "tenant_id": metadata.tenant_id,
        "user_id": metadata.user_id,
        "profile": metadata.profile,
        "status": metadata.status,
        "final_decision": metadata.final_decision,
        "artifact_type": metadata.artifact_type,
        "artifact_schema_version": metadata.artifact_schema_version,
        "artifact_ref": metadata.artifact_ref,
        "created_at": metadata.created_at,
        "updated_at": metadata.updated_at,
    }


def _run_metadata_from_row(row: dict[str, Any]) -> ValidationRunMetadata:
    return ValidationRunMetadata(
        run_id=_as_str(row, "run_id"),
        request_id=_as_str(row, "request_id"),
        tenant_id=_as_str(row, "tenant_id"),
        user_id=_as_str(row, "user_id"),
        profile=cast(ValidationProfile, _as_str(row, "profile")),
        status=cast(ValidationRunStatus, _as_str(row, "status")),
        final_decision=cast(ValidationRunDecision, _as_str(row, "final_decision")),
        artifact_type=cast(ValidationArtifactType, _as_str(row, "artifact_type")),
        artifact_schema_version=_as_str(row, "artifact_schema_version"),
        artifact_ref=_as_str(row, "artifact_ref"),
        created_at=_as_str(row, "created_at"),
        updated_at=_as_str(row, "updated_at"),
    )


def _review_row_from_metadata(metadata: ValidationReviewStateMetadata) -> dict[str, object]:
    return {
        "run_id": metadata.run_id,
        "agent_status": metadata.agent_status,
        "agent_summary": metadata.agent_summary,
        "findings_count": metadata.findings_count,
        "trader_required": metadata.trader_required,
        "trader_status": metadata.trader_status,
        "comments_count": metadata.comments_count,
        "updated_at": metadata.updated_at,
    }


def _review_metadata_from_row(row: dict[str, Any]) -> ValidationReviewStateMetadata:
    return ValidationReviewStateMetadata(
        run_id=_as_str(row, "run_id"),
        agent_status=cast(ValidationDecision, _as_str(row, "agent_status")),
        agent_summary=_as_str(row, "agent_summary"),
        findings_count=_as_int(row, "findings_count"),
        trader_required=_as_bool(row, "trader_required"),
        trader_status=cast(ValidationTraderReviewStatus, _as_str(row, "trader_status")),
        comments_count=_as_int(row, "comments_count"),
        updated_at=_as_str(row, "updated_at"),
    )


def _blob_ref_row_from_metadata(metadata: ValidationBlobReferenceMetadata) -> dict[str, object]:
    return {
        "run_id": metadata.run_id,
        "kind": metadata.kind,
        "ref": metadata.ref,
        "content_type": metadata.content_type,
        "size_bytes": metadata.size_bytes,
        "checksum_sha256": metadata.checksum_sha256,
        "created_at": metadata.created_at,
    }


def _blob_ref_metadata_from_row(row: dict[str, Any]) -> ValidationBlobReferenceMetadata:
    return ValidationBlobReferenceMetadata(
        run_id=_as_str(row, "run_id"),
        kind=cast(ValidationBlobKind, _as_str(row, "kind")),
        ref=_as_str(row, "ref"),
        content_type=_as_str(row, "content_type"),
        size_bytes=_as_int(row, "size_bytes"),
        checksum_sha256=_as_str(row, "checksum_sha256"),
        created_at=_as_str(row, "created_at"),
    )


def _baseline_row_from_metadata(metadata: ValidationBaselineMetadata) -> dict[str, object]:
    return {
        "id": metadata.id,
        "run_id": metadata.run_id,
        "tenant_id": metadata.tenant_id,
        "user_id": metadata.user_id,
        "name": metadata.name,
        "profile": metadata.profile,
        "notes": metadata.notes,
        "created_at": metadata.created_at,
    }


def _baseline_metadata_from_row(row: dict[str, Any]) -> ValidationBaselineMetadata:
    return ValidationBaselineMetadata(
        id=_as_str(row, "id"),
        run_id=_as_str(row, "run_id"),
        tenant_id=_as_str(row, "tenant_id"),
        user_id=_as_str(row, "user_id"),
        name=_as_str(row, "name"),
        profile=cast(ValidationProfile, _as_str(row, "profile")),
        notes=_as_optional_str(row, "notes"),
        created_at=_as_str(row, "created_at"),
    )


def create_validation_metadata_store(
    *,
    runtime_profile: str | None = None,
    supabase_url: str | None = None,
    supabase_key: str | None = None,
    supabase_client: Any | None = None,
    allow_in_memory_fallback: bool = True,
) -> ValidationMetadataStore:
    """Resolve runtime metadata storage.

    Production profile is fail-closed when Supabase configuration is missing.
    """
    profile = _resolve_runtime_profile(runtime_profile)
    if supabase_client is not None:
        return SupabaseValidationMetadataStore(supabase_client)

    resolved_url = supabase_url or os.getenv("SUPABASE_URL")
    resolved_key = supabase_key or os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if resolved_url and resolved_key:
        try:
            from supabase import create_client
        except Exception as exc:  # pragma: no cover - import path depends on runtime package availability
            if _is_production_profile(profile):
                raise ValidationStorageFailClosedError(
                    "Validation metadata storage failed closed: Supabase client import error in production profile."
                ) from exc
            if allow_in_memory_fallback:
                return InMemoryValidationMetadataStore()
            raise ValidationStorageFailClosedError(
                "Validation metadata storage unavailable and in-memory fallback disabled."
            ) from exc
        return SupabaseValidationMetadataStore(create_client(resolved_url, resolved_key))

    if _is_production_profile(profile):
        raise ValidationStorageFailClosedError(
            "Validation metadata storage failed closed: Supabase credentials are required in production profile."
        )

    if not allow_in_memory_fallback:
        raise ValidationStorageFailClosedError(
            "Validation metadata storage unavailable and in-memory fallback disabled."
        )
    return InMemoryValidationMetadataStore()
