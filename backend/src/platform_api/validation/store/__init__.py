"""Validation store boundaries and adapters."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "InMemoryValidationStorePort",
    "ValidationFinalDecision",
    "ValidationStorageServiceAdapter",
    "ValidationStorePort",
    "ValidationStoreRecord",
]

if TYPE_CHECKING:
    from src.platform_api.validation.store.adapters import ValidationStorageServiceAdapter
    from src.platform_api.validation.store.ports import (
        InMemoryValidationStorePort,
        ValidationFinalDecision,
        ValidationStorePort,
        ValidationStoreRecord,
    )


def __getattr__(name: str) -> Any:
    if name == "ValidationStorageServiceAdapter":
        module = import_module("src.platform_api.validation.store.adapters")
        return getattr(module, name)
    if name in {
        "InMemoryValidationStorePort",
        "ValidationFinalDecision",
        "ValidationStorePort",
        "ValidationStoreRecord",
    }:
        module = import_module("src.platform_api.validation.store.ports")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
