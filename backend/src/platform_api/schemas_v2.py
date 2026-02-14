"""Pydantic schemas for Platform API v2 KB/Data extensions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.platform_api.schemas_v1 import MarketScanIdea


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    assets: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=100)


class KnowledgeSearchItem(BaseModel):
    kind: str
    id: str
    title: str
    summary: str
    score: float
    evidence: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    requestId: str
    items: list[KnowledgeSearchItem]


class KnowledgePattern(BaseModel):
    id: str
    name: str
    type: str
    description: str
    suitableRegimes: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    timeframes: list[str] = Field(default_factory=list)
    confidenceScore: float
    sourceRef: str | None = None
    schemaVersion: str
    createdAt: str
    updatedAt: str


class KnowledgePatternListResponse(BaseModel):
    requestId: str
    items: list[KnowledgePattern]


class KnowledgeRegime(BaseModel):
    id: str
    asset: str
    regime: str
    volatility: str
    indicators: dict[str, float] = Field(default_factory=dict)
    startAt: str
    endAt: str | None = None
    notes: str | None = None
    schemaVersion: str
    createdAt: str


class KnowledgeRegimeResponse(BaseModel):
    requestId: str
    regime: KnowledgeRegime


class BacktestDataExportRequest(BaseModel):
    datasetIds: list[str] = Field(min_length=1)
    assetClasses: list[str] = Field(default_factory=list)


class BacktestDataExport(BaseModel):
    id: str
    status: str
    datasetIds: list[str]
    assetClasses: list[str]
    downloadUrl: str | None = None
    lineage: dict[str, Any] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class BacktestDataExportResponse(BaseModel):
    requestId: str
    export: BacktestDataExport


class MarketScanV2Response(BaseModel):
    requestId: str
    regimeSummary: str
    strategyIdeas: list[MarketScanIdea]
    knowledgeEvidence: list[KnowledgeSearchItem]
    dataContextSummary: str
