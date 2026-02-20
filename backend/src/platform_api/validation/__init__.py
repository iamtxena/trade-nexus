"""Validation package public exports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "InMemoryValidationMetadataStore",
    "NoopValidationVectorHook",
    "PersistedValidationRun",
    "SupabaseValidationMetadataStore",
    "VALIDATION_STORAGE_FAIL_CLOSED_CODE",
    "ValidationBaselineMetadata",
    "ValidationBlobReferenceMetadata",
    "ValidationMetadataStore",
    "ValidationMetadataStoreError",
    "ValidationReplayMetadata",
    "ValidationReviewStateMetadata",
    "ValidationRunMetadata",
    "ValidationStorageFailClosedError",
    "ValidationStorageService",
    "ValidationVectorHook",
    "compute_sha256_digest",
    "create_validation_metadata_store",
    "is_valid_blob_reference",
    "validate_blob_payload_integrity",
]

if TYPE_CHECKING:
    from src.platform_api.validation.storage import (
        VALIDATION_STORAGE_FAIL_CLOSED_CODE,
        InMemoryValidationMetadataStore,
        NoopValidationVectorHook,
        PersistedValidationRun,
        SupabaseValidationMetadataStore,
        ValidationBaselineMetadata,
        ValidationBlobReferenceMetadata,
        ValidationMetadataStore,
        ValidationMetadataStoreError,
        ValidationReplayMetadata,
        ValidationReviewStateMetadata,
        ValidationRunMetadata,
        ValidationStorageFailClosedError,
        ValidationStorageService,
        ValidationVectorHook,
        compute_sha256_digest,
        create_validation_metadata_store,
        is_valid_blob_reference,
        validate_blob_payload_integrity,
    )


def __getattr__(name: str) -> Any:
    if name in __all__:
        module = import_module("src.platform_api.validation.storage")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
