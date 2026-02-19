"""Provider connector boundaries for portable validation module."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "ConnectorRequestContext",
    "LonaValidationConnector",
    "ValidationConnector",
    "ValidationConnectorPayload",
]

if TYPE_CHECKING:
    from src.platform_api.validation.connectors.lona import LonaValidationConnector
    from src.platform_api.validation.connectors.ports import (
        ConnectorRequestContext,
        ValidationConnector,
        ValidationConnectorPayload,
    )


def __getattr__(name: str) -> Any:
    if name == "LonaValidationConnector":
        module = import_module("src.platform_api.validation.connectors.lona")
        return getattr(module, name)
    if name in {
        "ConnectorRequestContext",
        "ValidationConnector",
        "ValidationConnectorPayload",
    }:
        module = import_module("src.platform_api.validation.connectors.ports")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
