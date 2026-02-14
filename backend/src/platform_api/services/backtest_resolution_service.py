"""Resolve dataset references for backtest orchestration."""

from __future__ import annotations

from src.platform_api.adapters.data_bridge_adapter import DataBridgeAdapter
from src.platform_api.adapters.lona_adapter import AdapterError
from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import RequestContext


class BacktestResolutionService:
    """Maps platform dataset refs to provider data refs using the bridge adapter."""

    def __init__(self, data_bridge_adapter: DataBridgeAdapter) -> None:
        self._data_bridge_adapter = data_bridge_adapter

    async def resolve_data_ids(self, *, dataset_ids: list[str], context: RequestContext) -> list[str]:
        try:
            return await self._data_bridge_adapter.resolve_dataset_refs(
                dataset_ids=dataset_ids,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            )
        except AdapterError as exc:
            raise PlatformAPIError(
                status_code=exc.status_code,
                code=exc.code,
                message=str(exc),
                request_id=context.request_id,
            )
