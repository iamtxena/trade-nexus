"""Contract tests for portable validation module packaging boundaries (#232)."""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_subprocess_import_check(*modules: str) -> subprocess.CompletedProcess[str]:
    script = dedent(
        f"""
        import importlib
        import json
        import sys

        modules = {list(modules)!r}
        for module in modules:
            importlib.import_module(module)

        print(
            json.dumps(
                {{
                    "store_metadata_loaded": "src.platform_api.validation.store.metadata" in sys.modules,
                    "connectors_lona_loaded": "src.platform_api.validation.connectors.lona" in sys.modules,
                }}
            )
        )
        """
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        cwd=str(_backend_root()),
    )


class _PassingConnector:
    def resolve(self, *, context: Any, payload: Mapping[str, Any]) -> object:
        _ = payload
        from src.platform_api.validation.connectors.ports import ValidationConnectorPayload
        from src.platform_api.validation.core.deterministic import (
            DeterministicValidationEvidence,
            ValidationArtifactContext,
        )

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
    def resolve(self, *, context: Any, payload: Mapping[str, Any]) -> object:
        from src.platform_api.validation.connectors.ports import ValidationConnectorPayload
        from src.platform_api.validation.core.deterministic import DeterministicValidationEvidence

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


class _RecordingStore:
    def __init__(self) -> None:
        self.persisted: list[Any] = []

    async def persist(self, record: Any) -> None:
        self.persisted.append(record)


class _RecordingRenderer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def render(
        self,
        *,
        artifact: Mapping[str, Any],
        output_format: str,
    ) -> object:
        from src.platform_api.validation.render import RenderedValidationArtifact

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


@pytest.mark.parametrize(
    "module_order",
    [
        (
            "src.platform_api.validation.connectors.ports",
            "src.platform_api.validation.core.portable",
        ),
        (
            "src.platform_api.validation.core.portable",
            "src.platform_api.validation.connectors.ports",
        ),
    ],
)
def test_core_module_import_is_isolated_from_store_and_connector_implementations(
    module_order: Sequence[str],
) -> None:
    result = _run_subprocess_import_check(*module_order)
    assert result.returncode == 0, result.stderr

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip() != ""]
    assert lines, "Expected subprocess to print import-state payload."
    state = json.loads(lines[-1])

    assert state["store_metadata_loaded"] is False
    assert state["connectors_lona_loaded"] is False


def test_portable_core_runs_with_protocol_fakes_across_store_and_render_boundaries() -> None:
    async def _run() -> None:
        from src.platform_api.validation.core.portable import PortableValidationModule

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
        from src.platform_api.validation.core.portable import PortableValidationModule

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
