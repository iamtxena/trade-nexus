"""Portable validation connector boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from src.platform_api.validation.core.deterministic import (
    DeterministicValidationEvidence,
    ValidationArtifactContext,
)


@dataclass(frozen=True)
class ConnectorRequestContext:
    """Execution identity propagated to provider connectors."""

    run_id: str
    request_id: str
    tenant_id: str
    user_id: str


@dataclass(frozen=True)
class ValidationConnectorPayload:
    """Normalized provider evidence returned to validation core."""

    artifact_context: ValidationArtifactContext
    evidence: DeterministicValidationEvidence


class ValidationConnector(Protocol):
    """Provider boundary for portable validation evidence extraction."""

    def resolve(
        self,
        *,
        context: ConnectorRequestContext,
        payload: Mapping[str, Any],
    ) -> ValidationConnectorPayload:
        ...


__all__ = [
    "ConnectorRequestContext",
    "ValidationConnector",
    "ValidationConnectorPayload",
]
