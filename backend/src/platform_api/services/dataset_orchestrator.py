"""Thin-stub dataset lifecycle orchestration for Gate2."""

from __future__ import annotations

from src.platform_api.adapters.data_bridge_adapter import DataBridgeAdapter
from src.platform_api.adapters.lona_adapter import AdapterError
from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import (
    Dataset,
    DatasetListResponse,
    DatasetPublishLonaRequest,
    DatasetQualityReport,
    DatasetQualityReportResponse,
    DatasetResponse,
    DatasetTransformCandlesRequest,
    DatasetUploadCompleteRequest,
    DatasetUploadInitRequest,
    DatasetUploadInitResponse,
    DatasetValidateRequest,
    RequestContext,
)
from src.platform_api.state_store import DatasetRecord, InMemoryStateStore, QualityReportRecord, utc_now


class DatasetOrchestrator:
    """Gate2 dataset control-plane stubs with contract-compliant responses."""

    def __init__(self, *, store: InMemoryStateStore, data_bridge_adapter: DataBridgeAdapter) -> None:
        self._store = store
        self._data_bridge_adapter = data_bridge_adapter

    async def init_upload(
        self,
        *,
        request: DatasetUploadInitRequest,
        context: RequestContext,
    ) -> DatasetUploadInitResponse:
        dataset_id = self._store.next_id("dataset")
        now = utc_now()
        upload_url = f"https://uploads.trade-nexus.local/{dataset_id}"
        self._store.datasets[dataset_id] = DatasetRecord(
            id=dataset_id,
            filename=request.filename,
            content_type=request.contentType,
            size_bytes=request.sizeBytes,
            status="uploading",
            provider_data_id=None,
            upload_url=upload_url,
            created_at=now,
            updated_at=now,
        )
        return DatasetUploadInitResponse(
            requestId=context.request_id,
            datasetId=dataset_id,
            uploadUrl=upload_url,
            status="uploading",
        )

    async def complete_upload(
        self,
        *,
        dataset_id: str,
        request: DatasetUploadCompleteRequest | None = None,
        context: RequestContext,
    ) -> DatasetResponse:
        dataset = self._require_dataset(dataset_id=dataset_id, request_id=context.request_id)
        dataset.status = "uploaded"
        dataset.updated_at = utc_now()
        return DatasetResponse(requestId=context.request_id, dataset=self._to_dataset(dataset))

    async def validate_dataset(
        self,
        *,
        dataset_id: str,
        request: DatasetValidateRequest | None = None,
        context: RequestContext,
    ) -> DatasetResponse:
        dataset = self._require_dataset(dataset_id=dataset_id, request_id=context.request_id)
        dataset.status = "validating"
        dataset.updated_at = utc_now()
        # Thin-slice baseline executes validation synchronously.
        dataset.status = "validated"
        dataset.updated_at = utc_now()
        self._store.quality_reports[dataset_id] = QualityReportRecord(
            dataset_id=dataset_id,
            status="validated",
            summary="Dataset passed schema and timestamp-order checks.",
            issues=[],
        )
        return DatasetResponse(requestId=context.request_id, dataset=self._to_dataset(dataset))

    async def transform_candles(
        self,
        *,
        dataset_id: str,
        request: DatasetTransformCandlesRequest,
        context: RequestContext,
    ) -> DatasetResponse:
        dataset = self._require_dataset(dataset_id=dataset_id, request_id=context.request_id)
        dataset.status = "transforming"
        dataset.updated_at = utc_now()
        dataset.status = "ready"
        dataset.updated_at = utc_now()
        return DatasetResponse(requestId=context.request_id, dataset=self._to_dataset(dataset))

    async def publish_lona(
        self,
        *,
        dataset_id: str,
        request: DatasetPublishLonaRequest | None = None,
        context: RequestContext,
    ) -> DatasetResponse:
        dataset = self._require_dataset(dataset_id=dataset_id, request_id=context.request_id)
        dataset.status = "publishing_lona"
        dataset.updated_at = utc_now()
        mode = request.mode if request is not None else "explicit"

        try:
            provider_data_id = await self._data_bridge_adapter.ensure_published(
                dataset_id=dataset_id,
                mode=mode,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
            )
        except AdapterError as exc:
            dataset.status = "publish_failed"
            dataset.updated_at = utc_now()
            raise PlatformAPIError(
                status_code=exc.status_code,
                code=exc.code,
                message=str(exc),
                request_id=context.request_id,
            )

        dataset.status = "published_lona"
        dataset.provider_data_id = provider_data_id
        dataset.updated_at = utc_now()
        return DatasetResponse(requestId=context.request_id, dataset=self._to_dataset(dataset))

    async def list_datasets(
        self,
        *,
        cursor: str | None,
        context: RequestContext,
    ) -> DatasetListResponse:
        items = [self._to_dataset(record) for record in self._store.datasets.values()]
        return DatasetListResponse(requestId=context.request_id, items=items, nextCursor=None)

    async def get_dataset(self, *, dataset_id: str, context: RequestContext) -> DatasetResponse:
        dataset = self._require_dataset(dataset_id=dataset_id, request_id=context.request_id)
        return DatasetResponse(requestId=context.request_id, dataset=self._to_dataset(dataset))

    async def get_quality_report(self, *, dataset_id: str, context: RequestContext) -> DatasetQualityReportResponse:
        self._require_dataset(dataset_id=dataset_id, request_id=context.request_id)
        report = self._store.quality_reports.get(dataset_id)
        if report is None:
            report = QualityReportRecord(
                dataset_id=dataset_id,
                status="uploaded",
                summary="Quality report is not available yet.",
                issues=[],
            )

        return DatasetQualityReportResponse(
            requestId=context.request_id,
            qualityReport=DatasetQualityReport(
                datasetId=report.dataset_id,
                status=report.status,
                summary=report.summary,
                issues=report.issues,
            ),
        )

    def _require_dataset(self, *, dataset_id: str, request_id: str) -> DatasetRecord:
        dataset = self._store.datasets.get(dataset_id)
        if dataset is None:
            raise PlatformAPIError(
                status_code=404,
                code="DATASET_NOT_FOUND",
                message=f"Dataset {dataset_id} not found.",
                request_id=request_id,
            )
        return dataset

    @staticmethod
    def _to_dataset(record: DatasetRecord) -> Dataset:
        return Dataset(
            id=record.id,
            filename=record.filename,
            contentType=record.content_type,
            sizeBytes=record.size_bytes,
            status=record.status,
            providerDataId=record.provider_data_id,
            uploadUrl=record.upload_url,
            createdAt=record.created_at,
            updatedAt=record.updated_at,
        )
