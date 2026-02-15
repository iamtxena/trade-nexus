"""Risk policy schema loading and validation helpers for AG-RISK-01."""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

RiskPolicyMode = Literal["advisory", "enforced"]
RiskActionOnBreach = Literal[
    "reject_order",
    "cancel_open_orders",
    "halt_deployments",
    "notify_ops",
]

SUPPORTED_RISK_POLICY_VERSION = "risk-policy.v1"
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_RISK_POLICY_SCHEMA_PATH = REPO_ROOT / "contracts/schemas/risk-policy.v1.schema.json"


class RiskPolicyValidationError(ValueError):
    """Raised when a risk policy or schema violates the contract."""


class RiskPolicyLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    maxNotionalUsd: float = Field(ge=0)
    maxPositionNotionalUsd: float = Field(ge=0)
    maxDrawdownPct: float = Field(ge=0, le=100)
    maxDailyLossUsd: float = Field(ge=0)


class RiskPolicyKillSwitch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    triggered: bool = False
    triggeredAt: str | None = None
    reason: str | None = Field(default=None, min_length=1)

    @field_validator("triggeredAt")
    @classmethod
    def _validate_triggered_at(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("triggeredAt must be an RFC3339 date-time string.") from exc
        return value


class RiskPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    mode: RiskPolicyMode
    limits: RiskPolicyLimits
    killSwitch: RiskPolicyKillSwitch
    actionsOnBreach: list[RiskActionOnBreach] = Field(min_length=1)


def is_supported_policy_version(version: str) -> bool:
    return version == SUPPORTED_RISK_POLICY_VERSION


def validate_risk_policy_schema_document(schema: dict[str, Any]) -> None:
    required_root_keys = {"$schema", "$id", "type", "required", "properties"}
    missing = required_root_keys - schema.keys()
    if missing:
        raise RiskPolicyValidationError(f"Risk policy schema missing keys: {sorted(missing)}")

    required_list = schema.get("required", [])
    if not isinstance(required_list, list):
        raise RiskPolicyValidationError("Risk policy schema required field must be a list.")
    required_fields = set(required_list)
    expected_fields = {"version", "mode", "limits", "killSwitch", "actionsOnBreach"}
    if not expected_fields.issubset(required_fields):
        raise RiskPolicyValidationError(
            "Risk policy schema must require version, mode, limits, killSwitch, and actionsOnBreach.",
        )

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise RiskPolicyValidationError("Risk policy schema properties must be an object.")
    version_property = properties.get("version")
    if not isinstance(version_property, dict):
        raise RiskPolicyValidationError("Risk policy schema properties.version must be an object.")
    version_const = version_property.get("const")
    if not isinstance(version_const, str):
        raise RiskPolicyValidationError("Risk policy schema must define properties.version.const.")
    if not is_supported_policy_version(version_const):
        raise RiskPolicyValidationError(f"Unsupported risk policy schema version: {version_const}")


def load_risk_policy_schema(*, schema_path: Path = DEFAULT_RISK_POLICY_SCHEMA_PATH) -> dict[str, Any]:
    try:
        raw = schema_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RiskPolicyValidationError(f"Unable to read risk policy schema at {schema_path}") from exc

    try:
        schema = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RiskPolicyValidationError("Risk policy schema is not valid JSON.") from exc

    if not isinstance(schema, dict):
        raise RiskPolicyValidationError("Risk policy schema must be a JSON object.")
    validate_risk_policy_schema_document(schema)
    return schema


@lru_cache(maxsize=1)
def get_supported_risk_policy_schema() -> dict[str, Any]:
    return load_risk_policy_schema()


def validate_risk_policy(policy: dict[str, Any]) -> RiskPolicy:
    schema = get_supported_risk_policy_schema()
    expected_version = schema["properties"]["version"]["const"]

    try:
        parsed = RiskPolicy.model_validate(policy, strict=True)
    except ValidationError as exc:
        raise RiskPolicyValidationError(f"Invalid risk policy payload: {exc}") from exc

    if parsed.version != expected_version:
        raise RiskPolicyValidationError(
            f"Unsupported risk policy version: {parsed.version}. Expected {expected_version}.",
        )

    if parsed.limits.maxPositionNotionalUsd > parsed.limits.maxNotionalUsd:
        raise RiskPolicyValidationError(
            "maxPositionNotionalUsd must be less than or equal to maxNotionalUsd.",
        )

    if len(set(parsed.actionsOnBreach)) != len(parsed.actionsOnBreach):
        raise RiskPolicyValidationError("actionsOnBreach must not contain duplicates.")

    return parsed
