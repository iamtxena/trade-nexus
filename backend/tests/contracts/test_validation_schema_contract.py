"""Contract checks for validation artifact schema freeze (#224, #223)."""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "contracts" / "schemas"
VALIDATION_RUN_SCHEMA_PATH = SCHEMA_DIR / "validation_run.json"
VALIDATION_LLM_SNAPSHOT_SCHEMA_PATH = SCHEMA_DIR / "validation_llm_snapshot.json"
VALIDATION_POLICY_SCHEMA_PATH = SCHEMA_DIR / "validation_policy_profile.json"
VALIDATION_AGENT_REVIEW_RESULT_SCHEMA_PATH = SCHEMA_DIR / "validation_agent_review_result.json"


class SchemaValidationError(ValueError):
    """Raised when a payload fails frozen schema checks."""


def _load_schema(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert isinstance(payload, dict), f"Schema at {path} must be a JSON object."
    return payload


def _parse_rfc3339_datetime(value: str) -> None:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SchemaValidationError(f"Expected RFC3339 date-time, got {value!r}") from exc


def _validate_against_schema(instance: Any, schema: dict[str, Any], *, path: str = "$") -> None:
    if "const" in schema and instance != schema["const"]:
        raise SchemaValidationError(f"{path}: expected const value {schema['const']!r}, got {instance!r}")

    if "enum" in schema and instance not in schema["enum"]:
        raise SchemaValidationError(f"{path}: expected enum {schema['enum']!r}, got {instance!r}")

    schema_type = schema.get("type")

    if isinstance(schema_type, list):
        if "null" in schema_type and instance is None:
            return
        supported_types = [item for item in schema_type if item != "null"]
        last_error: SchemaValidationError | None = None
        for candidate_type in supported_types:
            candidate_schema = copy.deepcopy(schema)
            candidate_schema["type"] = candidate_type
            try:
                _validate_against_schema(instance, candidate_schema, path=path)
                return
            except SchemaValidationError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise SchemaValidationError(f"{path}: unsupported schema type declaration {schema_type!r}")

    if schema_type == "object":
        if not isinstance(instance, dict):
            raise SchemaValidationError(f"{path}: expected object, got {type(instance).__name__}")

        required = schema.get("required", [])
        if not isinstance(required, list):
            raise SchemaValidationError(f"{path}: schema required field must be a list.")
        missing = [field for field in required if field not in instance]
        if missing:
            raise SchemaValidationError(f"{path}: missing required field(s): {missing}")

        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise SchemaValidationError(f"{path}: schema properties must be an object.")

        additional_properties = schema.get("additionalProperties", True)

        for key, value in instance.items():
            property_schema = properties.get(key)
            if isinstance(property_schema, dict):
                _validate_against_schema(value, property_schema, path=f"{path}.{key}")
                continue

            if additional_properties is False:
                raise SchemaValidationError(f"{path}: additional property {key!r} is not allowed.")

            if isinstance(additional_properties, dict):
                _validate_against_schema(value, additional_properties, path=f"{path}.{key}")

        return

    if schema_type == "array":
        if not isinstance(instance, list):
            raise SchemaValidationError(f"{path}: expected array, got {type(instance).__name__}")

        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(instance) < min_items:
            raise SchemaValidationError(f"{path}: expected at least {min_items} item(s), got {len(instance)}")

        if schema.get("uniqueItems") is True:
            normalized_items = [json.dumps(item, sort_keys=True) for item in instance]
            if len(set(normalized_items)) != len(normalized_items):
                raise SchemaValidationError(f"{path}: array items must be unique.")

        items_schema = schema.get("items")
        if isinstance(items_schema, dict):
            for index, item in enumerate(instance):
                _validate_against_schema(item, items_schema, path=f"{path}[{index}]")

        return

    if schema_type == "string":
        if not isinstance(instance, str):
            raise SchemaValidationError(f"{path}: expected string, got {type(instance).__name__}")
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(instance) < min_length:
            raise SchemaValidationError(
                f"{path}: expected string length >= {min_length}, got {len(instance)}"
            )
        if schema.get("format") == "date-time":
            _parse_rfc3339_datetime(instance)
        return

    if schema_type == "number":
        if not isinstance(instance, (int, float)) or isinstance(instance, bool):
            raise SchemaValidationError(f"{path}: expected number, got {type(instance).__name__}")
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and instance < minimum:
            raise SchemaValidationError(f"{path}: expected number >= {minimum}, got {instance}")
        if isinstance(maximum, (int, float)) and instance > maximum:
            raise SchemaValidationError(f"{path}: expected number <= {maximum}, got {instance}")
        return

    if schema_type == "integer":
        if not isinstance(instance, int) or isinstance(instance, bool):
            raise SchemaValidationError(f"{path}: expected integer, got {type(instance).__name__}")
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, int) and instance < minimum:
            raise SchemaValidationError(f"{path}: expected integer >= {minimum}, got {instance}")
        if isinstance(maximum, int) and instance > maximum:
            raise SchemaValidationError(f"{path}: expected integer <= {maximum}, got {instance}")
        return

    if schema_type == "boolean":
        if not isinstance(instance, bool):
            raise SchemaValidationError(f"{path}: expected boolean, got {type(instance).__name__}")
        return


def _valid_policy(*, profile: str = "STANDARD") -> dict[str, Any]:
    return {
        "profile": profile,
        "blockMergeOnFail": True,
        "blockReleaseOnFail": True,
        "blockMergeOnAgentFail": profile != "FAST",
        "blockReleaseOnAgentFail": profile == "EXPERT",
        "requireTraderReview": profile == "EXPERT",
        "hardFailOnMissingIndicators": True,
        "failClosedOnEvidenceUnavailable": True,
    }


def _valid_validation_run_payload() -> dict[str, Any]:
    return {
        "schemaVersion": "validation-run.v1",
        "runId": "valrun-20260217-0001",
        "createdAt": "2026-02-17T10:30:00Z",
        "requestId": "req-validation-run-001",
        "tenantId": "tenant-001",
        "userId": "user-001",
        "strategyRef": {
            "strategyId": "strat-001",
            "provider": "lona",
            "providerRefId": "lona-strategy-123",
        },
        "inputs": {
            "prompt": "Build zig-zag strategy for BTC 1h with trend filter",
            "requestedIndicators": ["zigzag", "ema"],
            "datasetIds": ["dataset-btc-1h-2025"],
            "backtestReportRef": "blob://validation/valrun-20260217-0001/backtest-report.json",
        },
        "outputs": {
            "strategyCodeRef": "blob://validation/valrun-20260217-0001/strategy.py",
            "backtestReportRef": "blob://validation/valrun-20260217-0001/backtest-report.json",
            "tradesRef": "blob://validation/valrun-20260217-0001/trades.json",
            "executionLogsRef": "blob://validation/valrun-20260217-0001/execution.log",
            "chartPayloadRef": "blob://validation/valrun-20260217-0001/chart-payload.json",
        },
        "deterministicChecks": {
            "indicatorFidelity": {"status": "pass", "missingIndicators": []},
            "tradeCoherence": {"status": "pass", "violations": []},
            "metricConsistency": {"status": "pass", "driftPct": 0.8},
        },
        "agentReview": {
            "status": "pass",
            "summary": "No indicator/render drift detected.",
            "findings": [],
            "budget": {
                "profile": "STANDARD",
                "limits": {
                    "maxRuntimeSeconds": 1.2,
                    "maxTokens": 2400,
                    "maxToolCalls": 4,
                    "maxFindings": 6,
                },
                "usage": {
                    "runtimeSeconds": 0.12,
                    "tokensUsed": 512,
                    "toolCallsUsed": 0,
                },
                "withinBudget": True,
                "breachReason": None,
            },
        },
        "traderReview": {
            "required": False,
            "status": "not_requested",
            "comments": [],
        },
        "policy": _valid_policy(profile="STANDARD"),
        "finalDecision": "pass",
    }


def _valid_validation_llm_snapshot_payload() -> dict[str, Any]:
    return {
        "schemaVersion": "validation-llm-snapshot.v1",
        "runId": "valrun-20260217-0001",
        "sourceSchemaVersion": "validation-run.v1",
        "generatedAt": "2026-02-17T10:31:00Z",
        "strategyId": "strat-001",
        "requestedIndicators": ["zigzag", "ema"],
        "deterministicChecks": {
            "indicatorFidelityStatus": "pass",
            "tradeCoherenceStatus": "pass",
            "metricConsistencyStatus": "pass",
        },
        "policy": _valid_policy(profile="STANDARD"),
        "evidenceRefs": [
            {
                "kind": "chart_payload",
                "ref": "blob://validation/valrun-20260217-0001/chart-payload.json",
            },
            {
                "kind": "backtest_report",
                "ref": "blob://validation/valrun-20260217-0001/backtest-report.json",
            },
        ],
        "findings": [
            {
                "priority": 1,
                "confidence": 0.88,
                "summary": "No blocking anomaly found in indicator rendering.",
            }
        ],
        "finalDecision": "pass",
    }


def _valid_agent_review_result_payload() -> dict[str, Any]:
    return {
        "status": "fail",
        "summary": "Agent review blocked: token_budget_exceeded.",
        "findings": [
            {
                "id": "agent-budget-token_budget_exceeded",
                "priority": 0,
                "confidence": 1.0,
                "summary": "Agent review blocked: token_budget_exceeded.",
                "evidenceRefs": ["blob://validation/valrun-20260217-0001/chart-payload.json"],
            }
        ],
        "budget": {
            "profile": "STANDARD",
            "limits": {
                "maxRuntimeSeconds": 1.2,
                "maxTokens": 2400,
                "maxToolCalls": 4,
                "maxFindings": 6,
            },
            "usage": {
                "runtimeSeconds": 0.01,
                "tokensUsed": 4096,
                "toolCallsUsed": 1,
            },
            "withinBudget": False,
            "breachReason": "token_budget_exceeded",
        },
    }


def test_validation_policy_schema_has_expected_profiles_and_blocking_flags() -> None:
    schema = _load_schema(VALIDATION_POLICY_SCHEMA_PATH)
    required = set(schema["required"])
    assert {"profile", "blockMergeOnFail", "blockReleaseOnFail"}.issubset(required)
    assert {"blockMergeOnAgentFail", "blockReleaseOnAgentFail"}.issubset(required)
    assert schema["properties"]["profile"]["enum"] == ["FAST", "STANDARD", "EXPERT"]
    assert schema["properties"]["hardFailOnMissingIndicators"]["const"] is True
    assert schema["properties"]["failClosedOnEvidenceUnavailable"]["const"] is True


def test_validation_run_schema_accepts_canonical_payload() -> None:
    schema = _load_schema(VALIDATION_RUN_SCHEMA_PATH)
    payload = _valid_validation_run_payload()
    _validate_against_schema(payload, schema)


def test_validation_llm_snapshot_schema_accepts_compact_payload() -> None:
    schema = _load_schema(VALIDATION_LLM_SNAPSHOT_SCHEMA_PATH)
    payload = _valid_validation_llm_snapshot_payload()
    _validate_against_schema(payload, schema)


def test_validation_agent_review_result_schema_accepts_payload() -> None:
    schema = _load_schema(VALIDATION_AGENT_REVIEW_RESULT_SCHEMA_PATH)
    payload = _valid_agent_review_result_payload()
    _validate_against_schema(payload, schema)


def test_validation_policy_schema_rejects_unknown_profile() -> None:
    schema = _load_schema(VALIDATION_POLICY_SCHEMA_PATH)
    payload = _valid_policy(profile="ULTRA")
    with pytest.raises(SchemaValidationError):
        _validate_against_schema(payload, schema)


def test_validation_run_schema_rejects_non_blocking_hard_fail_flags() -> None:
    schema = _load_schema(VALIDATION_RUN_SCHEMA_PATH)
    payload = _valid_validation_run_payload()
    payload["policy"]["hardFailOnMissingIndicators"] = False
    with pytest.raises(SchemaValidationError):
        _validate_against_schema(payload, schema)


def test_validation_run_schema_rejects_agent_review_without_budget_report() -> None:
    schema = _load_schema(VALIDATION_RUN_SCHEMA_PATH)
    payload = _valid_validation_run_payload()
    del payload["agentReview"]["budget"]
    with pytest.raises(SchemaValidationError):
        _validate_against_schema(payload, schema)


def test_validation_llm_snapshot_schema_rejects_additional_properties() -> None:
    schema = _load_schema(VALIDATION_LLM_SNAPSHOT_SCHEMA_PATH)
    payload = _valid_validation_llm_snapshot_payload()
    mutated = copy.deepcopy(payload)
    mutated["unexpectedField"] = "unexpected-value"
    with pytest.raises(SchemaValidationError):
        _validate_against_schema(mutated, schema)


def test_validation_agent_review_result_schema_rejects_additional_properties() -> None:
    schema = _load_schema(VALIDATION_AGENT_REVIEW_RESULT_SCHEMA_PATH)
    payload = _valid_agent_review_result_payload()
    payload["budget"]["limits"]["unexpectedBudgetField"] = "unexpected"
    with pytest.raises(SchemaValidationError):
        _validate_against_schema(payload, schema)


def test_validation_agent_review_result_schema_accepts_null_breach_reason() -> None:
    schema = _load_schema(VALIDATION_AGENT_REVIEW_RESULT_SCHEMA_PATH)
    payload = _valid_agent_review_result_payload()
    payload["budget"]["withinBudget"] = True
    payload["budget"]["breachReason"] = None
    _validate_against_schema(payload, schema)


def test_validation_agent_review_result_schema_rejects_non_string_non_null_breach_reason() -> None:
    schema = _load_schema(VALIDATION_AGENT_REVIEW_RESULT_SCHEMA_PATH)
    payload = _valid_agent_review_result_payload()
    payload["budget"]["breachReason"] = ["unexpected-list"]
    with pytest.raises(SchemaValidationError):
        _validate_against_schema(payload, schema)
