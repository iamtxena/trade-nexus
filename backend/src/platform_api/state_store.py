"""In-memory state for the thin-slice platform API baseline."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.platform_api.knowledge.models import (
        CorrelationEdgeRecord,
        KnowledgePatternRecord,
        LessonLearnedRecord,
        MacroEventRecord,
        MarketRegimeRecord,
    )


def utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class StrategyRecord:
    id: str
    name: str
    description: str
    status: str
    provider: str
    provider_ref_id: str
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class BacktestRecord:
    id: str
    strategy_id: str
    status: str
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    completed_at: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    error: str | None = None
    provider_report_id: str | None = None


@dataclass
class DeploymentRecord:
    id: str
    strategy_id: str
    mode: str
    status: str
    capital: float
    engine: str = "live-engine"
    provider_ref_id: str | None = None
    latest_pnl: float | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class PositionRecord:
    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    unrealized_pnl: float


@dataclass
class PortfolioRecord:
    id: str
    mode: str
    cash: float
    total_value: float
    pnl_total: float | None = None
    positions: list[PositionRecord] = field(default_factory=list)


@dataclass
class OrderRecord:
    id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: float | None
    status: str
    deployment_id: str | None
    provider_order_id: str | None = None
    created_at: str = field(default_factory=utc_now)


@dataclass
class DatasetRecord:
    id: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    provider_data_id: str | None = None
    upload_url: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class QualityReportRecord:
    dataset_id: str
    status: str
    summary: str
    issues: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DataExportRecord:
    id: str
    status: str
    dataset_ids: list[str]
    asset_classes: list[str]
    target: str = "backtest"
    provider_export_ref: str | None = None
    download_url: str | None = None
    lineage: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class DriftEventRecord:
    id: str
    resource_type: str
    resource_id: str
    provider_ref_id: str | None
    previous_state: str
    provider_state: str
    resolution: str
    detected_at: str = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskAuditRecord:
    id: str
    decision: str
    check_type: str
    resource_type: str
    resource_id: str | None
    request_id: str
    tenant_id: str
    user_id: str
    policy_version: str | None = None
    policy_mode: str | None = None
    outcome_code: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


@dataclass
class ConversationSessionRecord:
    id: str
    channel: str
    status: str = "active"
    topic: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    last_turn_at: str | None = None


@dataclass
class ConversationTurnRecord:
    id: str
    session_id: str
    role: str
    message: str
    suggestions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


class InMemoryStateStore:
    """Simple in-process persistence for Gate2 thin-slice behavior."""

    def __init__(self) -> None:
        self.strategies: dict[str, StrategyRecord] = {
            "strat-001": StrategyRecord(
                id="strat-001",
                name="BTC Trend Follow",
                description="Breakout strategy for BTCUSD.",
                status="tested",
                provider="lona",
                provider_ref_id="lona-strategy-123",
                tags=["momentum", "crypto"],
                created_at="2026-02-10T10:00:00Z",
                updated_at="2026-02-13T19:00:00Z",
            ),
        }
        self.backtests: dict[str, BacktestRecord] = {
            "bt-001": BacktestRecord(
                id="bt-001",
                strategy_id="strat-001",
                status="completed",
                created_at="2026-02-13T21:25:00Z",
                started_at="2026-02-13T21:25:30Z",
                completed_at="2026-02-13T21:27:00Z",
                metrics={
                    "sharpeRatio": 1.48,
                    "maxDrawdownPct": 9.2,
                    "winRatePct": 57.3,
                    "totalReturnPct": 24.5,
                },
            ),
        }
        self.deployments: dict[str, DeploymentRecord] = {
            "dep-001": DeploymentRecord(
                id="dep-001",
                strategy_id="strat-001",
                mode="paper",
                status="running",
                capital=20000,
                provider_ref_id="live-abc",
                latest_pnl=150.25,
                created_at="2026-02-13T20:00:00Z",
                updated_at="2026-02-13T21:10:00Z",
            ),
        }
        self.portfolios: dict[str, PortfolioRecord] = {
            "portfolio-paper-001": PortfolioRecord(
                id="portfolio-paper-001",
                mode="paper",
                cash=12450.75,
                total_value=20891.12,
                pnl_total=891.12,
                positions=[
                    PositionRecord(
                        symbol="BTCUSDT",
                        quantity=0.3,
                        avg_price=62000,
                        current_price=64800,
                        unrealized_pnl=840,
                    )
                ],
            )
        }
        self.orders: dict[str, OrderRecord] = {
            "ord-001": OrderRecord(
                id="ord-001",
                symbol="BTCUSDT",
                side="buy",
                order_type="limit",
                quantity=0.1,
                price=64500,
                status="pending",
                deployment_id="dep-001",
                provider_order_id="live-order-001",
                created_at="2026-02-13T21:31:00Z",
            ),
        }
        self.datasets: dict[str, DatasetRecord] = {
            "dataset-btc-1h-2025": DatasetRecord(
                id="dataset-btc-1h-2025",
                filename="btc-1h-2025.csv",
                content_type="text/csv",
                size_bytes=1024,
                status="published_lona",
                provider_data_id="lona-symbol-001",
                upload_url="https://uploads.trade-nexus.local/dataset-btc-1h-2025",
                created_at="2026-02-13T18:00:00Z",
                updated_at="2026-02-13T18:05:00Z",
            )
        }
        self.quality_reports: dict[str, QualityReportRecord] = {
            "dataset-btc-1h-2025": QualityReportRecord(
                dataset_id="dataset-btc-1h-2025",
                status="validated",
                summary="Dataset passed baseline validation checks.",
                issues=[],
            )
        }
        self.dataset_provider_map: dict[str, str] = {
            "dataset-btc-1h-2025": "lona-symbol-001",
        }
        self.knowledge_patterns: dict[str, KnowledgePatternRecord] = {}
        self.market_regimes: dict[str, MarketRegimeRecord] = {}
        self.lessons_learned: dict[str, LessonLearnedRecord] = {}
        self.macro_events: dict[str, MacroEventRecord] = {}
        self.correlations: dict[str, CorrelationEdgeRecord] = {}
        self.knowledge_ingestion_events: set[str] = set()
        self.data_exports: dict[str, DataExportRecord] = {}
        self.drift_events: dict[str, DriftEventRecord] = {}
        self.risk_audit_trail: dict[str, RiskAuditRecord] = {}
        self.conversation_sessions: dict[str, ConversationSessionRecord] = {}
        self.conversation_turns: dict[str, list[ConversationTurnRecord]] = {}
        self.risk_policy: dict[str, Any] = {
            "version": "risk-policy.v1",
            "mode": "enforced",
            "limits": {
                "maxNotionalUsd": 1_000_000,
                "maxPositionNotionalUsd": 250_000,
                "maxDrawdownPct": 20.0,
                "maxDailyLossUsd": 100_000,
            },
            "killSwitch": {
                "enabled": True,
                "triggered": False,
            },
            "actionsOnBreach": [
                "reject_order",
                "cancel_open_orders",
                "halt_deployments",
                "notify_ops",
            ],
        }

        self._id_counters: dict[str, int] = {
            "strategy": 2,
            "backtest": 2,
            "deployment": 2,
            "order": 2,
            "dataset": 2,
            "knowledge_pattern": 1,
            "knowledge_regime": 1,
            "knowledge_lesson": 1,
            "knowledge_event": 1,
            "knowledge_corr": 1,
            "export": 1,
            "drift": 1,
            "risk_audit": 1,
            "conversation_session": 1,
            "conversation_turn": 1,
        }
        self._idempotency: dict[str, dict[str, tuple[str, dict[str, Any]]]] = {
            "deployments": {},
            "orders": {},
        }

    def next_id(self, scope: str) -> str:
        idx = self._id_counters[scope]
        self._id_counters[scope] = idx + 1
        if scope == "strategy":
            return f"strat-{idx:03d}"
        if scope == "backtest":
            return f"bt-{idx:03d}"
        if scope == "deployment":
            return f"dep-{idx:03d}"
        if scope == "order":
            return f"ord-{idx:03d}"
        if scope == "dataset":
            return f"dataset-{idx:03d}"
        if scope == "knowledge_pattern":
            return f"kbp-{idx:04d}"
        if scope == "knowledge_regime":
            return f"kbr-{idx:04d}"
        if scope == "knowledge_lesson":
            return f"kbl-{idx:04d}"
        if scope == "knowledge_event":
            return f"kbe-{idx:04d}"
        if scope == "knowledge_corr":
            return f"kbc-{idx:04d}"
        if scope == "export":
            return f"exp-{idx:04d}"
        if scope == "drift":
            return f"drift-{idx:04d}"
        if scope == "risk_audit":
            return f"risk-audit-{idx:04d}"
        if scope == "conversation_session":
            return f"conv-{idx:04d}"
        if scope == "conversation_turn":
            return f"turn-{idx:04d}"
        return f"{scope}-{idx:03d}"

    @staticmethod
    def payload_fingerprint(payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def get_idempotent_response(
        self,
        *,
        scope: str,
        key: str,
        payload: dict[str, Any],
    ) -> tuple[bool, dict[str, Any] | None]:
        scope_map = self._idempotency[scope]
        fingerprint = self.payload_fingerprint(payload)
        existing = scope_map.get(key)
        if existing is None:
            return False, None
        stored_fingerprint, stored_response = existing
        if stored_fingerprint != fingerprint:
            return True, None
        return False, copy.deepcopy(stored_response)

    def save_idempotent_response(
        self,
        *,
        scope: str,
        key: str,
        payload: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        scope_map = self._idempotency[scope]
        scope_map[key] = (self.payload_fingerprint(payload), copy.deepcopy(response))
