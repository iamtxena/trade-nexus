"""Pydantic models for the Trade Nexus Platform API v1 surface."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


StrategyStatus = Literal["draft", "testing", "tested", "deployable", "archived", "failed"]
BacktestStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
DeploymentMode = Literal["paper", "live"]
DeploymentStatus = Literal["queued", "running", "paused", "stopping", "stopped", "failed"]
OrderSide = Literal["buy", "sell"]
OrderType = Literal["market", "limit"]
OrderStatus = Literal["pending", "filled", "cancelled", "failed"]
DatasetLifecycleStatus = Literal[
    "uploading",
    "uploaded",
    "validating",
    "validated",
    "validation_failed",
    "transforming",
    "ready",
    "transform_failed",
    "publishing_lona",
    "published_lona",
    "publish_failed",
    "archived",
]
DatasetPublishMode = Literal["explicit", "just_in_time"]


class RequestContext(BaseModel):
    """Per-request identity and correlation fields."""

    request_id: str
    tenant_id: str
    user_id: str
    owner_user_id: str | None = None
    actor_type: Literal["user", "bot"] = "user"
    actor_id: str | None = None
    user_email: str | None = None

    @model_validator(mode="after")
    def _normalize_actor_identity(self) -> "RequestContext":
        owner = self.owner_user_id or self.user_id
        actor_id = self.actor_id
        if self.actor_type == "user":
            actor_id = actor_id or self.user_id
        elif actor_id is None or actor_id.strip() == "":
            raise ValueError("actor_id is required when actor_type=bot.")

        self.owner_user_id = owner
        self.actor_id = actor_id
        return self


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    timestamp: str


class MarketScanRequestConstraints(BaseModel):
    maxPositionPct: float | None = Field(default=None, ge=0, le=100)
    maxDrawdownPct: float | None = Field(default=None, ge=0, le=100)


class MarketScanRequest(BaseModel):
    assetClasses: list[str] = Field(min_length=1)
    capital: float = Field(ge=0)
    constraints: MarketScanRequestConstraints | None = None


class MarketScanIdea(BaseModel):
    name: str
    assetClass: str
    description: str
    rationale: str | None = None


class MarketScanResponse(BaseModel):
    requestId: str
    regimeSummary: str
    strategyIdeas: list[MarketScanIdea]


class Strategy(BaseModel):
    id: str
    name: str
    description: str | None = None
    status: StrategyStatus
    provider: Literal["lona"]
    providerRefId: str | None = None
    tags: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class StrategyResponse(BaseModel):
    requestId: str
    strategy: Strategy


class StrategyListResponse(BaseModel):
    requestId: str
    items: list[Strategy]
    nextCursor: str | None = None


class CreateStrategyRequest(BaseModel):
    name: str | None = None
    description: str = Field(min_length=10)
    provider: Literal["xai"] = "xai"


class UpdateStrategyRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: StrategyStatus | None = None
    tags: list[str] | None = None


class BacktestMetrics(BaseModel):
    sharpeRatio: float | None = None
    maxDrawdownPct: float | None = None
    winRatePct: float | None = None
    totalReturnPct: float | None = None


class Backtest(BaseModel):
    id: str
    strategyId: str
    status: BacktestStatus
    startedAt: str | None = None
    completedAt: str | None = None
    metrics: BacktestMetrics = Field(default_factory=BacktestMetrics)
    error: str | None = None
    createdAt: str


class BacktestResponse(BaseModel):
    requestId: str
    backtest: Backtest


class CreateBacktestRequest(BaseModel):
    dataIds: list[str] | None = None
    datasetIds: list[str] | None = None
    startDate: str
    endDate: str
    initialCash: float = Field(default=100000, ge=0)

    @model_validator(mode="after")
    def _validate_data_source(self) -> "CreateBacktestRequest":
        has_data_ids = self.dataIds is not None
        has_dataset_ids = self.datasetIds is not None
        if has_data_ids == has_dataset_ids:
            raise ValueError("Exactly one of dataIds or datasetIds must be provided.")
        if self.dataIds is not None and len(self.dataIds) == 0:
            raise ValueError("dataIds must include at least one id.")
        if self.datasetIds is not None and len(self.datasetIds) == 0:
            raise ValueError("datasetIds must include at least one id.")
        return self


class Deployment(BaseModel):
    id: str
    strategyId: str
    mode: DeploymentMode
    status: DeploymentStatus
    capital: float
    engine: str | None = None
    providerRefId: str | None = None
    latestPnl: float | None = None
    createdAt: str
    updatedAt: str | None = None


class DeploymentResponse(BaseModel):
    requestId: str
    deployment: Deployment


class DeploymentListResponse(BaseModel):
    requestId: str
    items: list[Deployment]
    nextCursor: str | None = None


class CreateDeploymentRequest(BaseModel):
    strategyId: str
    mode: DeploymentMode
    capital: float = Field(ge=0)


class StopDeploymentRequest(BaseModel):
    reason: str | None = None


class Position(BaseModel):
    symbol: str
    quantity: float
    avgPrice: float
    currentPrice: float
    unrealizedPnl: float


class Portfolio(BaseModel):
    id: str
    mode: DeploymentMode
    cash: float
    totalValue: float
    pnlTotal: float | None = None
    positions: list[Position] = Field(default_factory=list)


class PortfolioResponse(BaseModel):
    requestId: str
    portfolio: Portfolio


class PortfolioListResponse(BaseModel):
    requestId: str
    items: list[Portfolio]


class Order(BaseModel):
    id: str
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: float
    price: float | None = None
    status: OrderStatus
    deploymentId: str | None = None
    createdAt: str


class OrderResponse(BaseModel):
    requestId: str
    order: Order


class OrderListResponse(BaseModel):
    requestId: str
    items: list[Order]
    nextCursor: str | None = None


class CreateOrderRequest(BaseModel):
    symbol: str = Field(min_length=1)
    side: OrderSide
    type: OrderType
    quantity: float = Field(gt=0)
    price: float | None = Field(default=None, ge=0)
    deploymentId: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_price_rule(self) -> "CreateOrderRequest":
        if self.type == "limit" and self.price is None:
            raise ValueError("price is required for limit orders")
        if self.type == "market" and self.price is not None:
            raise ValueError("price is not allowed for market orders")
        return self


class Dataset(BaseModel):
    id: str
    filename: str
    contentType: str
    sizeBytes: int
    status: DatasetLifecycleStatus
    providerDataId: str | None = None
    uploadUrl: str | None = None
    createdAt: str
    updatedAt: str


class DatasetResponse(BaseModel):
    requestId: str
    dataset: Dataset


class DatasetListResponse(BaseModel):
    requestId: str
    items: list[Dataset]
    nextCursor: str | None = None


class DatasetQualityReport(BaseModel):
    datasetId: str
    status: DatasetLifecycleStatus
    summary: str
    issues: list[dict[str, Any]] = Field(default_factory=list)


class DatasetQualityReportResponse(BaseModel):
    requestId: str
    qualityReport: DatasetQualityReport


class DatasetUploadInitRequest(BaseModel):
    filename: str = Field(min_length=1)
    contentType: str = Field(min_length=1)
    sizeBytes: int = Field(gt=0)


class DatasetUploadInitResponse(BaseModel):
    requestId: str
    datasetId: str
    uploadUrl: str
    status: DatasetLifecycleStatus


class DatasetUploadCompleteRequest(BaseModel):
    uploadToken: str | None = None


class DatasetValidateRequest(BaseModel):
    columnMapping: dict[str, str] | None = None


class DatasetTransformCandlesRequest(BaseModel):
    frequency: str = Field(min_length=1)


class DatasetPublishLonaRequest(BaseModel):
    mode: DatasetPublishMode = "explicit"
