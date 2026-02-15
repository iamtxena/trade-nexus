"""Conversation contract service for additive /v2 conversation endpoints."""

from __future__ import annotations

from src.platform_api.errors import PlatformAPIError
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
    ConversationSessionRecord,
    ConversationTurnRecord,
    InMemoryStateStore,
    utc_now,
)


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
        record = ConversationSessionRecord(
            id=session_id,
            channel=request.channel,
            status="active",
            topic=request.topic,
            metadata=request.metadata,
            created_at=now,
            updated_at=now,
            last_turn_at=None,
        )
        self._store.conversation_sessions[session_id] = record
        self._store.conversation_turns.setdefault(session_id, [])
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

        turn = ConversationTurnRecord(
            id=self._store.next_id("conversation_turn"),
            session_id=session_id,
            role=request.role,
            message=request.message,
            suggestions=self._derive_suggestions(role=request.role, message=request.message),
            metadata=request.metadata,
        )
        self._store.conversation_turns.setdefault(session_id, []).append(turn)

        now = utc_now()
        session.updated_at = now
        session.last_turn_at = now

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
