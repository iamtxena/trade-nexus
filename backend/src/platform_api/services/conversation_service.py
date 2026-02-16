"""Conversation contract service for additive /v2 conversation endpoints."""

from __future__ import annotations

import copy
import logging
import re
from typing import Any

from src.platform_api.errors import PlatformAPIError
from src.platform_api.observability import log_context_event
from src.platform_api.schemas_v1 import RequestContext
from src.platform_api.schemas_v2 import (
    ConversationSession,
    ConversationSessionResponse,
    ConversationTurn,
    ConversationTurnResponse,
    CreateConversationSessionRequest,
    CreateConversationTurnRequest,
)
from src.platform_api.state_store import (
    ConversationNotificationRecord,
    ConversationSessionRecord,
    ConversationTurnRecord,
    InMemoryStateStore,
    utc_now,
)

_MEMORY_VERSION = "conv-memory.v1"
_MEMORY_MAX_RECENT_MESSAGES = 5
_MEMORY_MAX_LINKED_ARTIFACTS = 25
_MEMORY_MAX_SYMBOLS = 25
_MAX_SUGGESTIONS_PER_TURN = 8
logger = logging.getLogger(__name__)


class ConversationService:
    """Stateful in-memory conversation service for contract validation."""

    def __init__(self, *, store: InMemoryStateStore) -> None:
        self._store = store

    async def create_session(
        self,
        *,
        request: CreateConversationSessionRequest,
        context: RequestContext,
    ) -> ConversationSessionResponse:
        session_id = self._store.next_id("conversation_session")
        now = utc_now()
        metadata = dict(request.metadata)
        metadata["notificationsOptIn"] = bool(metadata.get("notificationsOptIn", False))
        metadata["notificationAuditCount"] = int(metadata.get("notificationAuditCount", 0))
        metadata["contextMemory"] = self._load_context_memory(context=context)
        record = ConversationSessionRecord(
            id=session_id,
            channel=request.channel,
            status="active",
            topic=request.topic,
            metadata=metadata,
            created_at=now,
            updated_at=now,
            last_turn_at=None,
        )
        self._store.conversation_sessions[session_id] = record
        self._store.conversation_turns.setdefault(session_id, [])
        log_context_event(
            logger,
            level=logging.INFO,
            message="Conversation session created.",
            context=context,
            component="conversation",
            operation="create_session",
            resource_type="conversation_session",
            resource_id=session_id,
            channel=request.channel,
        )
        return ConversationSessionResponse(requestId=context.request_id, session=self._to_session(record))

    async def get_session(self, *, session_id: str, context: RequestContext) -> ConversationSessionResponse:
        record = self._store.conversation_sessions.get(session_id)
        if record is None:
            raise PlatformAPIError(
                status_code=404,
                code="CONVERSATION_SESSION_NOT_FOUND",
                message=f"Conversation session {session_id} not found.",
                request_id=context.request_id,
            )
        return ConversationSessionResponse(requestId=context.request_id, session=self._to_session(record))

    async def create_turn(
        self,
        *,
        session_id: str,
        request: CreateConversationTurnRequest,
        context: RequestContext,
    ) -> ConversationTurnResponse:
        session = self._store.conversation_sessions.get(session_id)
        if session is None:
            raise PlatformAPIError(
                status_code=404,
                code="CONVERSATION_SESSION_NOT_FOUND",
                message=f"Conversation session {session_id} not found.",
                request_id=context.request_id,
            )

        now = utc_now()
        context_memory = self._update_context_memory(
            session=session,
            role=request.role,
            message=request.message,
            created_at=now,
            context=context,
        )
        proactive_notifications = self._derive_proactive_notifications(
            role=request.role,
            message=request.message,
            context_memory=context_memory,
        )
        proactive_suggestions = [notification["message"] for notification in proactive_notifications]
        suggestions = self._append_unique(
            self._derive_suggestions(role=request.role, message=request.message),
            proactive_suggestions,
            max_items=_MAX_SUGGESTIONS_PER_TURN,
        )
        turn_metadata = dict(request.metadata)
        turn_metadata["contextMemorySnapshot"] = context_memory
        turn_metadata["notificationsOptIn"] = self._notifications_opted_in(session=session)
        turn_metadata["notifications"] = []
        turn = ConversationTurnRecord(
            id=self._store.next_id("conversation_turn"),
            session_id=session_id,
            role=request.role,
            message=request.message,
            suggestions=suggestions,
            metadata=turn_metadata,
            created_at=now,
        )
        if self._notifications_opted_in(session=session):
            notification_ids = self._record_notifications(
                session=session,
                turn=turn,
                context=context,
                notifications=proactive_notifications,
            )
            turn.metadata["notifications"] = proactive_notifications
            turn.metadata["notificationIds"] = notification_ids

        self._store.conversation_turns.setdefault(session_id, []).append(turn)

        session.updated_at = now
        session.last_turn_at = now

        log_context_event(
            logger,
            level=logging.INFO,
            message="Conversation turn created.",
            context=context,
            component="conversation",
            operation="create_turn",
            resource_type="conversation_turn",
            resource_id=turn.id,
            sessionId=session_id,
            role=request.role,
        )
        return ConversationTurnResponse(
            requestId=context.request_id,
            sessionId=session_id,
            turn=self._to_turn(turn),
        )

    @staticmethod
    def _to_session(record: ConversationSessionRecord) -> ConversationSession:
        return ConversationSession(
            id=record.id,
            channel=record.channel,
            status=record.status,
            topic=record.topic,
            metadata=record.metadata,
            createdAt=record.created_at,
            updatedAt=record.updated_at,
            lastTurnAt=record.last_turn_at,
        )

    @staticmethod
    def _to_turn(record: ConversationTurnRecord) -> ConversationTurn:
        return ConversationTurn(
            id=record.id,
            sessionId=record.session_id,
            role=record.role,
            message=record.message,
            suggestions=record.suggestions,
            metadata=record.metadata,
            createdAt=record.created_at,
        )

    @staticmethod
    def _derive_suggestions(*, role: str, message: str) -> list[str]:
        if role != "user":
            return []

        lowered = message.lower()
        suggestions: list[str] = []

        if "deploy" in lowered:
            suggestions.append("Run deployment status check before placing orders.")
        if "order" in lowered or "buy" in lowered or "sell" in lowered:
            suggestions.append("Confirm risk-policy and idempotency key before execution.")
        if "backtest" in lowered:
            suggestions.append("Review latest backtest metrics and drawdown before deployment.")

        return suggestions

    @staticmethod
    def _memory_key(*, context: RequestContext) -> str:
        return f"{context.tenant_id}:{context.user_id}"

    def _default_context_memory(self) -> dict[str, Any]:
        return {
            "version": _MEMORY_VERSION,
            "retention": {"maxRecentMessages": _MEMORY_MAX_RECENT_MESSAGES},
            "turnCount": 0,
            "lastIntent": None,
            "recentMessages": [],
            "linkedArtifacts": {
                "strategyIds": [],
                "deploymentIds": [],
                "orderIds": [],
                "portfolioIds": [],
                "backtestIds": [],
                "datasetIds": [],
            },
            "symbols": [],
        }

    def _load_context_memory(self, *, context: RequestContext) -> dict[str, Any]:
        key = self._memory_key(context=context)
        existing = self._store.conversation_user_memory.get(key)
        if isinstance(existing, dict):
            return copy.deepcopy(existing)
        return self._default_context_memory()

    @staticmethod
    def _notifications_opted_in(*, session: ConversationSessionRecord) -> bool:
        return bool(session.metadata.get("notificationsOptIn", False))

    def _update_context_memory(
        self,
        *,
        session: ConversationSessionRecord,
        role: str,
        message: str,
        created_at: str,
        context: RequestContext,
    ) -> dict[str, Any]:
        context_memory = session.metadata.get("contextMemory")
        if not isinstance(context_memory, dict):
            context_memory = self._load_context_memory(context=context)
        else:
            context_memory = copy.deepcopy(context_memory)

        context_memory["version"] = _MEMORY_VERSION
        retention = context_memory.get("retention")
        if not isinstance(retention, dict):
            retention = {}
            context_memory["retention"] = retention
        max_recent = int(retention.get("maxRecentMessages", _MEMORY_MAX_RECENT_MESSAGES))
        if max_recent <= 0:
            max_recent = _MEMORY_MAX_RECENT_MESSAGES
        retention["maxRecentMessages"] = max_recent

        context_memory["turnCount"] = int(context_memory.get("turnCount", 0)) + 1

        recent_messages = context_memory.get("recentMessages")
        if not isinstance(recent_messages, list):
            recent_messages = []
            context_memory["recentMessages"] = recent_messages
        recent_messages.append({"role": role, "message": message, "createdAt": created_at})
        if len(recent_messages) > max_recent:
            del recent_messages[:-max_recent]

        linked_artifacts = context_memory.get("linkedArtifacts")
        if not isinstance(linked_artifacts, dict):
            linked_artifacts = {}
            context_memory["linkedArtifacts"] = linked_artifacts
        for field in (
            "strategyIds",
            "deploymentIds",
            "orderIds",
            "portfolioIds",
            "backtestIds",
            "datasetIds",
        ):
            values = linked_artifacts.get(field)
            if not isinstance(values, list):
                linked_artifacts[field] = []

        if role == "user":
            intent = self._infer_intent(message=message)
            if intent is not None:
                context_memory["lastIntent"] = intent

            linked_artifacts["strategyIds"] = self._append_unique(
                linked_artifacts["strategyIds"],
                self._find_ids(message=message, pattern=r"\bstrat-[a-z0-9]+\b"),
                max_items=_MEMORY_MAX_LINKED_ARTIFACTS,
            )
            linked_artifacts["deploymentIds"] = self._append_unique(
                linked_artifacts["deploymentIds"],
                self._find_ids(message=message, pattern=r"\bdep-[a-z0-9]+\b"),
                max_items=_MEMORY_MAX_LINKED_ARTIFACTS,
            )
            linked_artifacts["orderIds"] = self._append_unique(
                linked_artifacts["orderIds"],
                self._find_ids(message=message, pattern=r"\bord-[a-z0-9]+\b"),
                max_items=_MEMORY_MAX_LINKED_ARTIFACTS,
            )
            linked_artifacts["portfolioIds"] = self._append_unique(
                linked_artifacts["portfolioIds"],
                self._find_ids(message=message, pattern=r"\bportfolio-[a-z0-9-]+\b"),
                max_items=_MEMORY_MAX_LINKED_ARTIFACTS,
            )
            linked_artifacts["backtestIds"] = self._append_unique(
                linked_artifacts["backtestIds"],
                self._find_ids(message=message, pattern=r"\bbt-[a-z0-9]+\b"),
                max_items=_MEMORY_MAX_LINKED_ARTIFACTS,
            )
            linked_artifacts["datasetIds"] = self._append_unique(
                linked_artifacts["datasetIds"],
                self._find_ids(message=message, pattern=r"\bdataset-[a-z0-9-]+\b"),
                max_items=_MEMORY_MAX_LINKED_ARTIFACTS,
            )
            symbols = context_memory.get("symbols")
            if not isinstance(symbols, list):
                symbols = []
            context_memory["symbols"] = self._append_unique(
                symbols,
                self._find_ids(message=message, pattern=r"\b[A-Z]{2,10}(?:USDT|USD)\b"),
                max_items=_MEMORY_MAX_SYMBOLS,
            )

        session.metadata["contextMemory"] = context_memory
        self._store.conversation_user_memory[self._memory_key(context=context)] = copy.deepcopy(context_memory)
        return context_memory

    @staticmethod
    def _find_ids(*, message: str, pattern: str) -> list[str]:
        return [match.group(0) for match in re.finditer(pattern, message, flags=re.IGNORECASE)]

    @staticmethod
    def _append_unique(existing: list[Any], new_values: list[Any], *, max_items: int) -> list[Any]:
        normalized = [str(value) for value in existing]
        for value in new_values:
            item = str(value)
            if item not in normalized:
                normalized.append(item)
        if len(normalized) > max_items:
            normalized = normalized[-max_items:]
        return normalized

    @staticmethod
    def _infer_intent(*, message: str) -> str | None:
        lowered = message.lower()
        if "deploy" in lowered:
            return "deploy"
        if "backtest" in lowered:
            return "backtest"
        if "order" in lowered or "buy" in lowered or "sell" in lowered:
            return "order"
        if "risk" in lowered or "drawdown" in lowered:
            return "risk"
        if "portfolio" in lowered:
            return "portfolio"
        return None

    def _derive_proactive_notifications(
        self,
        *,
        role: str,
        message: str,
        context_memory: dict[str, Any],
    ) -> list[dict[str, str]]:
        if role != "user":
            return []

        lowered = message.lower()
        notifications: list[dict[str, str]] = []

        kill_switch = self._store.risk_policy.get("killSwitch")
        if isinstance(kill_switch, dict) and bool(kill_switch.get("triggered")):
            notifications.append(
                {
                    "category": "risk",
                    "severity": "critical",
                    "message": "Kill-switch is active; execution side effects remain blocked until recovery.",
                }
            )

        last_intent = context_memory.get("lastIntent")
        if "deploy" in lowered or last_intent == "deploy":
            notifications.append(
                {
                    "category": "execution",
                    "severity": "info",
                    "message": "Proactive check: confirm deployment mode, capital limits, and status before execution.",
                }
            )
        if "order" in lowered or "buy" in lowered or "sell" in lowered or last_intent == "order":
            notifications.append(
                {
                    "category": "risk",
                    "severity": "warning",
                    "message": "Proactive check: verify risk limits and include a stable idempotency key for order placement.",
                }
            )
        if "drawdown" in lowered or "risk" in lowered or last_intent == "risk":
            notifications.append(
                {
                    "category": "risk",
                    "severity": "warning",
                    "message": "Proactive check: review drawdown and daily loss thresholds before continuing.",
                }
            )

        # Deduplicate notifications by exact message while preserving order.
        unique: list[dict[str, str]] = []
        seen_messages: set[str] = set()
        for notification in notifications:
            message_value = notification["message"]
            if message_value in seen_messages:
                continue
            seen_messages.add(message_value)
            unique.append(notification)
        return unique

    def _record_notifications(
        self,
        *,
        session: ConversationSessionRecord,
        turn: ConversationTurnRecord,
        context: RequestContext,
        notifications: list[dict[str, str]],
    ) -> list[str]:
        notification_ids: list[str] = []
        for notification in notifications:
            notification_id = self._store.next_id("conversation_notification")
            record = ConversationNotificationRecord(
                id=notification_id,
                session_id=session.id,
                turn_id=turn.id,
                category=notification["category"],
                severity=notification["severity"],
                message=notification["message"],
                request_id=context.request_id,
                tenant_id=context.tenant_id,
                user_id=context.user_id,
                metadata={"channel": session.channel},
                created_at=turn.created_at,
            )
            self._store.conversation_notifications[notification_id] = record
            notification_ids.append(notification_id)

        session.metadata["notificationAuditCount"] = int(session.metadata.get("notificationAuditCount", 0)) + len(
            notification_ids
        )
        return notification_ids
