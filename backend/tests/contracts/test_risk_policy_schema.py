"""Contract tests for AG-RISK-01 risk policy schema and validation."""

from __future__ import annotations

import copy

import pytest

from src.platform_api.services.risk_policy import (
    SUPPORTED_RISK_POLICY_VERSION,
    RiskPolicyValidationError,
    is_supported_policy_version,
    load_risk_policy_schema,
    validate_risk_policy,
    validate_risk_policy_schema_document,
)


def _valid_policy() -> dict[str, object]:
    return {
        "version": SUPPORTED_RISK_POLICY_VERSION,
        "mode": "enforced",
        "limits": {
            "maxNotionalUsd": 250000,
            "maxPositionNotionalUsd": 50000,
            "maxDrawdownPct": 12.5,
            "maxDailyLossUsd": 5000,
        },
        "killSwitch": {
            "enabled": True,
            "triggered": False,
        },
        "actionsOnBreach": [
            "reject_order",
            "cancel_open_orders",
            "halt_deployments",
            "notify_ops",
        ],
    }


def test_schema_document_loads_and_has_required_contract_fields() -> None:
    schema = load_risk_policy_schema()
    assert schema["type"] == "object"
    required = set(schema["required"])
    assert {"version", "mode", "limits", "killSwitch", "actionsOnBreach"}.issubset(required)
    assert schema["properties"]["version"]["const"] == SUPPORTED_RISK_POLICY_VERSION


def test_valid_policy_passes_validation() -> None:
    policy = validate_risk_policy(_valid_policy())
    assert policy.version == SUPPORTED_RISK_POLICY_VERSION
    assert policy.mode == "enforced"
    assert policy.killSwitch.enabled is True


def test_invalid_mode_is_rejected() -> None:
    payload = _valid_policy()
    payload["mode"] = "permissive"
    with pytest.raises(RiskPolicyValidationError):
        validate_risk_policy(payload)


def test_invalid_version_is_rejected() -> None:
    payload = _valid_policy()
    payload["version"] = "risk-policy.v2"
    with pytest.raises(RiskPolicyValidationError):
        validate_risk_policy(payload)


def test_invalid_limits_are_rejected() -> None:
    payload = _valid_policy()
    limits = payload["limits"]
    assert isinstance(limits, dict)
    limits["maxPositionNotionalUsd"] = 300000
    with pytest.raises(RiskPolicyValidationError):
        validate_risk_policy(payload)


def test_kill_switch_reason_requires_non_empty_string() -> None:
    payload = _valid_policy()
    kill_switch = payload["killSwitch"]
    assert isinstance(kill_switch, dict)
    kill_switch["reason"] = ""
    with pytest.raises(RiskPolicyValidationError):
        validate_risk_policy(payload)


def test_kill_switch_triggered_at_requires_rfc3339_datetime() -> None:
    payload = _valid_policy()
    kill_switch = payload["killSwitch"]
    assert isinstance(kill_switch, dict)
    kill_switch["triggeredAt"] = "2026-99-99"
    with pytest.raises(RiskPolicyValidationError):
        validate_risk_policy(payload)


def test_strict_types_reject_string_coercion() -> None:
    payload = _valid_policy()
    limits = payload["limits"]
    assert isinstance(limits, dict)
    limits["maxNotionalUsd"] = "250000"
    kill_switch = payload["killSwitch"]
    assert isinstance(kill_switch, dict)
    kill_switch["enabled"] = "true"
    with pytest.raises(RiskPolicyValidationError):
        validate_risk_policy(payload)


def test_schema_with_unknown_version_fails_contract_validation() -> None:
    schema = load_risk_policy_schema()
    mutated = copy.deepcopy(schema)
    mutated["properties"]["version"]["const"] = "risk-policy.v9"
    with pytest.raises(RiskPolicyValidationError):
        validate_risk_policy_schema_document(mutated)


def test_schema_with_non_object_properties_fails_contract_validation() -> None:
    schema = load_risk_policy_schema()
    mutated = copy.deepcopy(schema)
    mutated["properties"] = []
    with pytest.raises(RiskPolicyValidationError):
        validate_risk_policy_schema_document(mutated)


def test_version_compatibility_only_supports_v1() -> None:
    assert is_supported_policy_version("risk-policy.v1")
    assert not is_supported_policy_version("risk-policy.v2")
