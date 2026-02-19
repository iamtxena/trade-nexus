"""Storage ports for portable validation module."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from src.platform_api.state_store import utc_now

ValidationFinalDecision = Literal["pass", "conditional_pass", "fail"]


@dataclass(frozen=True)
class ValidationStoreRecord:
    """Portable record persisted by validation store adapters."""

    run_id: str
    request_id: str
    tenant_id: str
    user_id: str
    profile: str
    final_decision: ValidationFinalDecision
    artifact_ref: str
    artifact: Mapping[str, Any]
    snapshot: Mapping[str, Any]
    agent_review: Mapping[str, Any]
    created_at: str = field(default_factory=utc_now)


class ValidationStorePort(Protocol):
    """Persistence boundary consumed by validation core."""

    async def persist(self, record: ValidationStoreRecord) -> None:
        ...


class InMemoryValidationStorePort(ValidationStorePort):
    """Deterministic in-memory store used by local contract tests."""

    def __init__(self) -> None:
        self._records: dict[str, ValidationStoreRecord] = {}

    async def persist(self, record: ValidationStoreRecord) -> None:
        self._records[record.run_id] = copy.deepcopy(record)

    async def get(self, *, run_id: str) -> ValidationStoreRecord | None:
        record = self._records.get(run_id)
        if record is None:
            return None
        return copy.deepcopy(record)


__all__ = [
    "InMemoryValidationStorePort",
    "ValidationFinalDecision",
    "ValidationStorePort",
    "ValidationStoreRecord",
]
