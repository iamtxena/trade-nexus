"""Thin data bridge adapter for dataset-reference resolution."""

from __future__ import annotations

from typing import Protocol

from src.platform_api.adapters.lona_adapter import AdapterError
from src.platform_api.state_store import InMemoryStateStore


class DataBridgeAdapter(Protocol):
    """Boundary for dataset->provider data resolution."""

    async def resolve_dataset_refs(
        self,
        *,
        dataset_ids: list[str],
        tenant_id: str,
        user_id: str,
    ) -> list[str]:
        ...

    async def ensure_published(
        self,
        *,
        dataset_id: str,
        mode: str,
        tenant_id: str,
        user_id: str,
    ) -> str:
        ...


class InMemoryDataBridgeAdapter:
    """Gate2 baseline data bridge using in-memory mappings."""

    def __init__(self, store: InMemoryStateStore) -> None:
        self._store = store

    async def resolve_dataset_refs(
        self,
        *,
        dataset_ids: list[str],
        tenant_id: str,
        user_id: str,
    ) -> list[str]:
        provider_ids: list[str] = []
        unresolved: list[str] = []
        for dataset_id in dataset_ids:
            provider_id = self._store.dataset_provider_map.get(dataset_id)
            if provider_id:
                provider_ids.append(provider_id)
            else:
                unresolved.append(dataset_id)

        if unresolved:
            raise AdapterError(
                "Dataset references are not published.",
                code="DATASET_NOT_PUBLISHED",
                status_code=404,
            )

        return provider_ids

    async def ensure_published(
        self,
        *,
        dataset_id: str,
        mode: str,
        tenant_id: str,
        user_id: str,
    ) -> str:
        dataset = self._store.datasets.get(dataset_id)
        if dataset is None:
            raise AdapterError(
                f"Dataset {dataset_id} not found.",
                code="DATASET_NOT_FOUND",
                status_code=404,
            )

        existing = self._store.dataset_provider_map.get(dataset_id)
        if existing:
            return existing

        provider_id = f"lona-symbol-{dataset_id}"
        self._store.dataset_provider_map[dataset_id] = provider_id
        return provider_id
