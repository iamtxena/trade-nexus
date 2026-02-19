"""Lona-specific connector implementation for portable validation module."""

from __future__ import annotations

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


def _mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _first_non_empty(*values: object) -> str:
    for value in values:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                return normalized
    return ""


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        token = item.strip()
        if token:
            normalized.append(token)
    return tuple(dict.fromkeys(normalized))


def _dict_tuple(value: object) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    rows: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            rows.append(dict(item))
    return tuple(rows)


def _float_mapping(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, float] = {}
    for key, raw in value.items():
        if not isinstance(key, str):
            continue
        label = key.strip()
        if not label:
            continue
        if isinstance(raw, bool):
            continue
        if isinstance(raw, (int, float)):
            normalized[label] = float(raw)
    return normalized


class LonaValidationConnector(ValidationConnector):
    """Converts Lona-oriented payloads into portable validation core inputs."""

    def resolve(
        self,
        *,
        context: ConnectorRequestContext,
        payload: Mapping[str, Any],
    ) -> ValidationConnectorPayload:
        strategy = _mapping(payload.get("strategy"))
        inputs = _mapping(payload.get("inputs"))
        outputs = _mapping(payload.get("outputs"))
        evidence = _mapping(payload.get("evidence"))

        strategy_id = _first_non_empty(
            strategy.get("strategyId"),
            payload.get("strategyId"),
            payload.get("strategy_id"),
            f"strategy-{context.run_id}",
        )
        provider = _first_non_empty(strategy.get("provider"), payload.get("provider"), "lona")
        provider_ref_id = _first_non_empty(
            strategy.get("providerRefId"),
            strategy.get("provider_ref_id"),
            payload.get("providerRefId"),
            payload.get("provider_ref_id"),
            f"provider-{context.run_id}",
        )
        prompt = _first_non_empty(
            inputs.get("prompt"),
            payload.get("prompt"),
            "validation prompt unavailable",
        )

        requested_indicators = _string_tuple(inputs.get("requestedIndicators")) or _string_tuple(
            payload.get("requestedIndicators")
        )
        if not requested_indicators:
            requested_indicators = ("unknown",)

        dataset_ids = _string_tuple(inputs.get("datasetIds")) or _string_tuple(payload.get("datasetIds"))
        if not dataset_ids:
            dataset_ids = ("dataset-unknown",)

        base_ref = f"blob://validation/{context.run_id}"
        backtest_report_ref = _first_non_empty(
            outputs.get("backtestReportRef"),
            inputs.get("backtestReportRef"),
            payload.get("backtestReportRef"),
            f"{base_ref}/backtest-report.json",
        )
        strategy_code_ref = _first_non_empty(
            outputs.get("strategyCodeRef"),
            payload.get("strategyCodeRef"),
            f"{base_ref}/strategy.py",
        )
        trades_ref = _first_non_empty(outputs.get("tradesRef"), payload.get("tradesRef"), f"{base_ref}/trades.json")
        execution_logs_ref = _first_non_empty(
            outputs.get("executionLogsRef"),
            payload.get("executionLogsRef"),
            f"{base_ref}/execution.log",
        )
        chart_payload_ref = _first_non_empty(
            outputs.get("chartPayloadRef"),
            payload.get("chartPayloadRef"),
            f"{base_ref}/chart-payload.json",
        )

        artifact_context = ValidationArtifactContext(
            run_id=context.run_id,
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            user_id=context.user_id,
            strategy_id=strategy_id,
            provider=provider,
            provider_ref_id=provider_ref_id,
            prompt=prompt,
            requested_indicators=requested_indicators,
            dataset_ids=dataset_ids,
            backtest_report_ref=backtest_report_ref,
            strategy_code_ref=strategy_code_ref,
            trades_ref=trades_ref,
            execution_logs_ref=execution_logs_ref,
            chart_payload_ref=chart_payload_ref,
        )

        rendered_indicators = _string_tuple(evidence.get("renderedIndicators")) or _string_tuple(
            payload.get("renderedIndicators")
        )
        chart_payload = evidence.get("chartPayload")
        if not isinstance(chart_payload, dict):
            candidate_payload = payload.get("chartPayload")
            chart_payload = candidate_payload if isinstance(candidate_payload, dict) else None

        connector_payload = ValidationConnectorPayload(
            artifact_context=artifact_context,
            evidence=DeterministicValidationEvidence(
                requested_indicators=requested_indicators,
                rendered_indicators=rendered_indicators,
                chart_payload=chart_payload,
                trades=_dict_tuple(evidence.get("trades") or payload.get("trades")),
                execution_logs=_dict_tuple(
                    evidence.get("executionLogs") or payload.get("executionLogs")
                ),
                reported_metrics=_float_mapping(
                    evidence.get("reportedMetrics") or payload.get("reportedMetrics")
                ),
                recomputed_metrics=_float_mapping(
                    evidence.get("recomputedMetrics") or payload.get("recomputedMetrics")
                ),
                dataset_ids=dataset_ids,
                lineage=(
                    dict(evidence["lineage"])
                    if isinstance(evidence.get("lineage"), dict)
                    else (dict(payload["lineage"]) if isinstance(payload.get("lineage"), dict) else None)
                ),
            ),
        )
        return connector_payload


__all__ = ["LonaValidationConnector"]
