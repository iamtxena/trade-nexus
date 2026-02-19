"""Contract tests for portable validation module packaging boundaries (#232)."""

from __future__ import annotations

import asyncio
import importlib
import sys
from collections.abc import Mapping
from typing import Any

from src.platform_api.validation.connectors.ports import (
    ConnectorRequestContext,
    ValidationConnector,
    ValidationConnectorPayload,
)
from src.platform_api.validation.core.deterministic import (
    DeterministicValidationEvidence,
    ValidationArtifactContext,
)
from src.platform_api.validation.core.portable import PortableValidationModule
from src.platform_api.validation.render import RenderedValidationArtifact
from src.platform_api.validation.render.ports import ValidationRenderFormat, ValidationRenderPort
from src.platform_api.validation.store.ports import ValidationStorePort, ValidationStoreRecord


class _PassingConnector(ValidationConnector):
    def resolve(
        self,
        *,
        context: ConnectorRequestContext,
        payload: Mapping[str, Any],
    ) -> ValidationConnectorPayload:
        _ = payload
        return ValidationConnectorPayload(
            artifact_context=ValidationArtifactContext(
                run_id=context.run_id,
                request_id=context.request_id,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                strategy_id="strat-232",
                provider_ref_id="provider-232",
                provider="lona",
                prompt="Build an EMA strategy for BTC 1h.",
                requested_indicators=("ema",),
                dataset_ids=("dataset-btc-1h",),
                backtest_report_ref="blob://validation/valrun-232/backtest-report.json",
                strategy_code_ref="blob://validation/valrun-232/strategy.py",
                trades_ref="blob://validation/valrun-232/trades.json",
                execution_logs_ref="blob://validation/valrun-232/execution.log",
                chart_payload_ref="blob://validation/valrun-232/chart-payload.json",
            ),
            evidence=DeterministicValidationEvidence(
                requested_indicators=("ema",),
                rendered_indicators=("ema",),
                chart_payload={"indicators": [{"name": "ema"}]},
                trades=(
                    {
                        "orderId": "ord-232-1",
                    },
                ),
                execution_logs=(
                    {"orderId": "ord-232-1", "status": "created"},
                    {"orderId": "ord-232-1", "status": "accepted"},
                    {"orderId": "ord-232-1", "status": "filled"},
                ),
                reported_metrics={"sharpeRatio": 1.0},
                recomputed_metrics={"sharpeRatio": 1.0},
                dataset_ids=("dataset-btc-1h",),
                lineage={
                    "datasets": [
                        {
                            "datasetId": "dataset-btc-1h",
                            "sourceRef": "blob://datasets/raw/btc.csv",
                        }
                    ]
                },
            ),
        )


class _MissingIndicatorConnector(_PassingConnector):
    def resolve(
        self,
        *,
        context: ConnectorRequestContext,
        payload: Mapping[str, Any],
    ) -> ValidationConnectorPayload:
        resolved = super().resolve(context=context, payload=payload)
        return ValidationConnectorPayload(
            artifact_context=resolved.artifact_context,
            evidence=DeterministicValidationEvidence(
                requested_indicators=resolved.evidence.requested_indicators,
                rendered_indicators=(),
                chart_payload={"indicators": []},
                trades=resolved.evidence.trades,
                execution_logs=resolved.evidence.execution_logs,
                reported_metrics=resolved.evidence.reported_metrics,
                recomputed_metrics=resolved.evidence.recomputed_metrics,
                dataset_ids=resolved.evidence.dataset_ids,
                lineage=resolved.evidence.lineage,
            ),
        )


class _RecordingStore(ValidationStorePort):
    def __init__(self) -> None:
        self.persisted: list[ValidationStoreRecord] = []

    async def persist(self, record: ValidationStoreRecord) -> None:
        self.persisted.append(record)


class _RecordingRenderer(ValidationRenderPort):
    def __init__(self) -> None:
        self.calls: list[ValidationRenderFormat] = []

    def render(
        self,
        *,
        artifact: Mapping[str, Any],
        output_format: ValidationRenderFormat,
    ) -> RenderedValidationArtifact | None:
        self.calls.append(output_format)
        run_id = artifact.get("runId")
        assert isinstance(run_id, str)
        return RenderedValidationArtifact(
            output_format=output_format,
            ref=f"blob://validation/{run_id}/report.{output_format}",
        )


def _policy_payload() -> dict[str, Any]:
    return {
        "profile": "STANDARD",
        "blockMergeOnFail": True,
        "blockReleaseOnFail": True,
        "blockMergeOnAgentFail": True,
        "blockReleaseOnAgentFail": False,
        "requireTraderReview": False,
        "hardFailOnMissingIndicators": True,
        "failClosedOnEvidenceUnavailable": True,
    }


def test_core_module_import_is_isolated_from_store_and_connector_implementations() -> None:
    sys.modules.pop("src.platform_api.validation.core.portable", None)
    sys.modules.pop("src.platform_api.validation.store.metadata", None)
    sys.modules.pop("src.platform_api.validation.connectors.lona", None)

    importlib.import_module("src.platform_api.validation.core.portable")

    assert "src.platform_api.validation.store.metadata" not in sys.modules
    assert "src.platform_api.validation.connectors.lona" not in sys.modules


def test_portable_core_runs_with_protocol_fakes_across_store_and_render_boundaries() -> None:
    async def _run() -> None:
        store = _RecordingStore()
        renderer = _RecordingRenderer()
        module = PortableValidationModule(
            connector=_PassingConnector(),
            store=store,
            renderer=renderer,
        )

        result = await module.run(
            run_id="valrun-232-iso-001",
            request_id="req-232-iso-001",
            tenant_id="tenant-232",
            user_id="user-232",
            payload={},
            policy_payload=_policy_payload(),
            render_formats=("html", "pdf"),
            persist=True,
        )

        assert result.artifact["finalDecision"] == "pass"
        assert result.snapshot["schemaVersion"] == "validation-llm-snapshot.v1"
        assert len(result.rendered_artifacts) == 2
        assert renderer.calls == ["html", "pdf"]
        assert len(store.persisted) == 1
        persisted = store.persisted[0]
        assert persisted.run_id == "valrun-232-iso-001"
        assert persisted.final_decision == "pass"

    asyncio.run(_run())


def test_connector_substitution_changes_outcome_without_core_changes() -> None:
    async def _run() -> None:
        module_pass = PortableValidationModule(connector=_PassingConnector())
        module_fail = PortableValidationModule(connector=_MissingIndicatorConnector())

        passed = await module_pass.run(
            run_id="valrun-232-sub-001",
            request_id="req-232-sub-001",
            tenant_id="tenant-232",
            user_id="user-232",
            payload={},
            policy_payload=_policy_payload(),
            persist=False,
        )
        failed = await module_fail.run(
            run_id="valrun-232-sub-002",
            request_id="req-232-sub-002",
            tenant_id="tenant-232",
            user_id="user-232",
            payload={},
            policy_payload=_policy_payload(),
            persist=False,
        )

        assert passed.artifact["finalDecision"] == "pass"
        assert failed.artifact["finalDecision"] == "fail"
        assert passed.artifact["deterministicChecks"]["indicatorFidelity"]["status"] == "pass"
        assert failed.artifact["deterministicChecks"]["indicatorFidelity"]["status"] == "fail"

    asyncio.run(_run())
