"""Contract tests for validation metadata storage adapters (issue #226)."""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Sequence
from dataclasses import replace

import pytest

from src.platform_api.validation.storage import (
    InMemoryValidationMetadataStore,
    SupabaseValidationMetadataStore,
    ValidationBaselineMetadata,
    ValidationBlobReferenceMetadata,
    ValidationReviewStateMetadata,
    ValidationRunDecision,
    ValidationRunMetadata,
    ValidationRunStatus,
    ValidationStorageFailClosedError,
    ValidationStorageService,
    ValidationTraderReviewStatus,
    ValidationVectorHook,
    create_validation_metadata_store,
    validate_blob_payload_integrity,
)


class _FakeSupabaseResult:
    def __init__(self, data: object) -> None:
        self.data = data
        self.error: object | None = None


class _FakeSupabaseQuery:
    def __init__(self, tables: dict[str, list[dict[str, object]]], table: str) -> None:
        self._tables = tables
        self._table = table
        self._operation = "select"
        self._filters: list[tuple[str, object]] = []
        self._payload: object | None = None
        self._on_conflict: str | None = None

    def select(self, _columns: str) -> _FakeSupabaseQuery:
        self._operation = "select"
        return self

    def eq(self, key: str, value: object) -> _FakeSupabaseQuery:
        self._filters.append((key, value))
        return self

    def upsert(self, payload: object, *, on_conflict: str | None = None) -> _FakeSupabaseQuery:
        self._operation = "upsert"
        self._payload = payload
        self._on_conflict = on_conflict
        return self

    def execute(self) -> _FakeSupabaseResult:
        if self._operation == "upsert":
            return _FakeSupabaseResult(self._execute_upsert())
        return _FakeSupabaseResult(self._execute_select())

    def _execute_select(self) -> list[dict[str, object]]:
        rows = self._tables.setdefault(self._table, [])
        selected: list[dict[str, object]] = []
        for row in rows:
            if all(row.get(key) == value for key, value in self._filters):
                selected.append(copy.deepcopy(row))
        return selected

    def _execute_upsert(self) -> list[dict[str, object]]:
        rows = self._tables.setdefault(self._table, [])
        conflict_keys = [key.strip() for key in (self._on_conflict or "").split(",") if key.strip()]
        payload_items = self._payload if isinstance(self._payload, list) else [self._payload]
        if not all(isinstance(item, dict) for item in payload_items):
            raise AssertionError("Fake Supabase upsert payload must be a dict or list[dict].")

        stored: list[dict[str, object]] = []
        for item in payload_items:
            row = copy.deepcopy(item)
            assert isinstance(row, dict)

            existing_index: int | None = None
            for index, existing in enumerate(rows):
                if conflict_keys and all(existing.get(key) == row.get(key) for key in conflict_keys):
                    existing_index = index
                    break

            if existing_index is None:
                rows.append(row)
            else:
                rows[existing_index] = row
            stored.append(copy.deepcopy(row))
        return stored


class _FakeSupabaseClient:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, object]]] = {}

    def table(self, table_name: str) -> _FakeSupabaseQuery:
        return _FakeSupabaseQuery(self._tables, table_name)


class _RecordingVectorHook(ValidationVectorHook):
    def __init__(self) -> None:
        self.persisted: list[dict[str, object]] = []

    async def on_validation_run_persisted(
        self,
        *,
        run: ValidationRunMetadata,
        review_state: ValidationReviewStateMetadata | None,
        blob_refs: Sequence[ValidationBlobReferenceMetadata],
    ) -> None:
        self.persisted.append(
            {
                "runId": run.run_id,
                "decision": run.final_decision,
                "reviewed": review_state is not None,
                "blobCount": len(blob_refs),
            }
        )


def _run_metadata(
    *,
    status: ValidationRunStatus = "queued",
    final_decision: ValidationRunDecision = "pending",
    updated_at: str = "2026-02-18T19:30:00Z",
) -> ValidationRunMetadata:
    return ValidationRunMetadata(
        run_id="valrun-20260218-0001",
        request_id="req-validation-run-226",
        tenant_id="tenant-226",
        user_id="user-226",
        profile="STANDARD",
        status=status,
        final_decision=final_decision,
        artifact_ref="blob://validation/valrun-20260218-0001/validation-run.json",
        artifact_schema_version="validation-run.v1",
        created_at="2026-02-18T19:25:00Z",
        updated_at=updated_at,
    )


def _review_metadata(
    *,
    trader_status: ValidationTraderReviewStatus = "requested",
    findings_count: int = 1,
    comments_count: int = 0,
) -> ValidationReviewStateMetadata:
    return ValidationReviewStateMetadata(
        run_id="valrun-20260218-0001",
        agent_status="conditional_pass",
        agent_summary="Indicator fidelity passed but requires trader sign-off.",
        findings_count=findings_count,
        trader_required=True,
        trader_status=trader_status,
        comments_count=comments_count,
        updated_at="2026-02-18T19:31:00Z",
    )


def _blob_refs(*, chart_payload: bytes) -> list[ValidationBlobReferenceMetadata]:
    return [
        ValidationBlobReferenceMetadata.from_payload(
            run_id="valrun-20260218-0001",
            kind="backtest_report",
            ref="blob://validation/valrun-20260218-0001/backtest-report.json",
            payload=b'{"metrics":{"sharpeRatio":1.2}}',
            content_type="application/json",
        ),
        ValidationBlobReferenceMetadata.from_payload(
            run_id="valrun-20260218-0001",
            kind="chart_payload",
            ref="blob://validation/valrun-20260218-0001/chart-payload.json",
            payload=chart_payload,
            content_type="application/json",
        ),
    ]


def test_validation_storage_persistence_lifecycle() -> None:
    async def _run() -> None:
        metadata_store = SupabaseValidationMetadataStore(_FakeSupabaseClient())
        vector_hook = _RecordingVectorHook()
        service = ValidationStorageService(metadata_store=metadata_store, vector_hook=vector_hook)

        initial_run = _run_metadata(status="queued", final_decision="pending")
        initial_review = _review_metadata(trader_status="requested", findings_count=1)
        initial_refs = _blob_refs(chart_payload=b'{"chart":"v1"}')

        await service.persist_run(
            metadata=initial_run,
            review_state=initial_review,
            blob_refs=initial_refs,
        )

        persisted_initial = await service.get_run(
            run_id=initial_run.run_id,
            tenant_id=initial_run.tenant_id,
            user_id=initial_run.user_id,
        )
        assert persisted_initial is not None
        assert persisted_initial.metadata.status == "queued"
        assert persisted_initial.metadata.final_decision == "pending"
        assert persisted_initial.review_state is not None
        assert persisted_initial.review_state.trader_status == "requested"
        assert len(persisted_initial.blob_refs) == 2

        completed_run = replace(
            initial_run,
            status="completed",
            final_decision="pass",
            updated_at="2026-02-18T19:38:00Z",
        )
        completed_review = replace(
            initial_review,
            trader_status="approved",
            comments_count=1,
            updated_at="2026-02-18T19:38:00Z",
        )
        updated_refs = _blob_refs(chart_payload=b'{"chart":"v2"}')
        updated_refs.append(
            ValidationBlobReferenceMetadata.from_payload(
                run_id=completed_run.run_id,
                kind="trades",
                ref="blob://validation/valrun-20260218-0001/trades.json",
                payload=b'{"rows":[{"symbol":"BTCUSDT"}]}',
                content_type="application/json",
            )
        )

        await service.persist_run(
            metadata=completed_run,
            review_state=completed_review,
            blob_refs=updated_refs,
        )

        persisted_completed = await service.get_run(
            run_id=completed_run.run_id,
            tenant_id=completed_run.tenant_id,
            user_id=completed_run.user_id,
        )
        assert persisted_completed is not None
        assert persisted_completed.metadata.status == "completed"
        assert persisted_completed.metadata.final_decision == "pass"
        assert persisted_completed.review_state is not None
        assert persisted_completed.review_state.trader_status == "approved"
        assert len(persisted_completed.blob_refs) == 3

        baseline = ValidationBaselineMetadata(
            id="valbase-226-001",
            run_id=completed_run.run_id,
            tenant_id=completed_run.tenant_id,
            user_id=completed_run.user_id,
            name="btc-1h-validation-baseline",
            profile="STANDARD",
            notes="Approved baseline for replay contract coverage.",
            created_at="2026-02-18T19:39:00Z",
        )
        await service.persist_baseline(baseline)

        persisted_baseline = await service.get_baseline(
            baseline_id=baseline.id,
            tenant_id=baseline.tenant_id,
            user_id=baseline.user_id,
        )
        assert persisted_baseline is not None
        assert persisted_baseline.run_id == completed_run.run_id
        assert persisted_baseline.profile == "STANDARD"
        assert len(vector_hook.persisted) == 2
        assert vector_hook.persisted[-1]["decision"] == "pass"

        not_found = await service.get_run(
            run_id=completed_run.run_id,
            tenant_id=completed_run.tenant_id,
            user_id="wrong-user",
        )
        assert not_found is None

    asyncio.run(_run())


def test_blob_reference_integrity_and_checksum_contract() -> None:
    payload = b'{"blob":"canonical"}'
    ref = ValidationBlobReferenceMetadata.from_payload(
        run_id="valrun-20260218-0002",
        kind="execution_logs",
        ref="blob://validation/valrun-20260218-0002/execution.log",
        payload=payload,
        content_type="text/plain",
    )

    assert ref.verify_payload(payload) is True
    assert ref.verify_payload(payload + b"tamper") is False

    validate_blob_payload_integrity(ref, payload)
    with pytest.raises(ValueError):
        validate_blob_payload_integrity(ref, payload + b"tamper")


def test_validation_storage_factory_fails_closed_in_production_without_supabase() -> None:
    with pytest.raises(ValidationStorageFailClosedError) as exc_info:
        create_validation_metadata_store(
            runtime_profile="production",
            supabase_url="",
            supabase_key="",
            allow_in_memory_fallback=True,
        )
    assert exc_info.value.code == "VALIDATION_STORAGE_FAIL_CLOSED"


def test_validation_storage_factory_uses_in_memory_in_non_production() -> None:
    store = create_validation_metadata_store(
        runtime_profile="development",
        supabase_url="",
        supabase_key="",
        allow_in_memory_fallback=True,
    )
    assert isinstance(store, InMemoryValidationMetadataStore)
