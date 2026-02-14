"""Pydantic schemas for Platform API v2 KB/Data extensions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

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


ConversationChannel = Literal["cli", "web", "openclaw"]
ConversationRole = Literal["user", "assistant", "system"]
ConversationSessionStatus = Literal["active", "closed"]


class CreateConversationSessionRequest(BaseModel):
    channel: ConversationChannel
    topic: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _reject_null_topic(cls, value: Any) -> Any:
        if isinstance(value, dict) and "topic" in value and value["topic"] is None:
            raise ValueError("topic must be omitted or a non-empty string.")
        return value


class ConversationSession(BaseModel):
    id: str
    channel: ConversationChannel
    status: ConversationSessionStatus
    topic: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str
    lastTurnAt: str | None = None


class ConversationSessionResponse(BaseModel):
    requestId: str
    session: ConversationSession


class CreateConversationTurnRequest(BaseModel):
    role: ConversationRole
    message: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationTurn(BaseModel):
    id: str
    sessionId: str
    role: ConversationRole
    message: str
    suggestions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str


class ConversationTurnResponse(BaseModel):
    requestId: str
    sessionId: str
    turn: ConversationTurn
