"""Optional render boundary for portable validation module."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

ValidationRenderFormat = Literal["html", "pdf"]


@dataclass(frozen=True)
class RenderedValidationArtifact:
    """Represents one optional rendered output artifact."""

    output_format: ValidationRenderFormat
    ref: str


class ValidationRenderPort(Protocol):
    """Render boundary consumed by validation core."""

    def render(
        self,
        *,
        artifact: Mapping[str, Any],
        output_format: ValidationRenderFormat,
    ) -> RenderedValidationArtifact | None:
        ...


class NoopValidationRenderer(ValidationRenderPort):
    """Default renderer that keeps render lane disabled."""

    def render(
        self,
        *,
        artifact: Mapping[str, Any],
        output_format: ValidationRenderFormat,
    ) -> RenderedValidationArtifact | None:
        _ = (artifact, output_format)
        return None


class InMemoryValidationRenderer(ValidationRenderPort):
    """Deterministic renderer used in contract tests."""

    def __init__(self, *, base_ref_prefix: str = "blob://validation") -> None:
        self._base_ref_prefix = base_ref_prefix.rstrip("/")

    def render(
        self,
        *,
        artifact: Mapping[str, Any],
        output_format: ValidationRenderFormat,
    ) -> RenderedValidationArtifact | None:
        run_id = artifact.get("runId")
        if not isinstance(run_id, str) or run_id.strip() == "":
            run_id = "unknown-run"
        extension = "html" if output_format == "html" else "pdf"
        return RenderedValidationArtifact(
            output_format=output_format,
            ref=f"{self._base_ref_prefix}/{run_id}/report.{extension}",
        )


__all__ = [
    "InMemoryValidationRenderer",
    "NoopValidationRenderer",
    "RenderedValidationArtifact",
    "ValidationRenderFormat",
    "ValidationRenderPort",
]
