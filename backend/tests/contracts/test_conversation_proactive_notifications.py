"""Contract tests for CONV-03 proactive suggestion and notification pipeline."""

from __future__ import annotations

import asyncio

from src.platform_api.schemas_v1 import RequestContext
from src.platform_api.schemas_v2 import CreateConversationSessionRequest, CreateConversationTurnRequest
from src.platform_api.services.conversation_service import ConversationService
from src.platform_api.state_store import InMemoryStateStore


def _context(*, user_id: str = "user-a") -> RequestContext:
    return RequestContext(
        request_id="req-conv-notify-001",
        tenant_id="tenant-a",
        user_id=user_id,
    )


def test_notifications_emitted_when_opted_in_and_audited() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        service = ConversationService(store=store)
        context = _context()

        session = await service.create_session(
            request=CreateConversationSessionRequest(
                channel="openclaw",
                topic="proactive",
                metadata={"notificationsOptIn": True},
            ),
            context=context,
        )
        response = await service.create_turn(
            session_id=session.session.id,
            request=CreateConversationTurnRequest(
                role="user",
                message="deploy strat-001 and place a buy order on BTCUSDT",
            ),
            context=context,
        )

        notifications = response.turn.metadata["notifications"]
        assert len(notifications) >= 2
        assert response.turn.metadata["notificationsOptIn"] is True
        assert "notificationIds" in response.turn.metadata
        assert len(store.conversation_notifications) == len(response.turn.metadata["notificationIds"])

        refreshed = await service.get_session(session_id=session.session.id, context=context)
        assert refreshed.session.metadata["notificationAuditCount"] == len(store.conversation_notifications)

    asyncio.run(_run())


def test_notifications_suppressed_when_opt_out_disabled() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        service = ConversationService(store=store)
        context = _context()

        session = await service.create_session(
            request=CreateConversationSessionRequest(channel="web", topic="opt-out"),
            context=context,
        )
        response = await service.create_turn(
            session_id=session.session.id,
            request=CreateConversationTurnRequest(
                role="user",
                message="deploy and place order",
            ),
            context=context,
        )

        assert len(response.turn.suggestions) >= 1
        assert response.turn.metadata["notificationsOptIn"] is False
        assert response.turn.metadata["notifications"] == []
        assert len(store.conversation_notifications) == 0

    asyncio.run(_run())


def test_kill_switch_drives_critical_notification() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        store.risk_policy["killSwitch"] = {
            "enabled": True,
            "triggered": True,
            "reason": "drawdown",
        }
        service = ConversationService(store=store)
        context = _context()

        session = await service.create_session(
            request=CreateConversationSessionRequest(
                channel="cli",
                topic="risk",
                metadata={"notificationsOptIn": True},
            ),
            context=context,
        )
        response = await service.create_turn(
            session_id=session.session.id,
            request=CreateConversationTurnRequest(
                role="user",
                message="place an order now",
            ),
            context=context,
        )

        notifications = response.turn.metadata["notifications"]
        assert any(note["category"] == "risk" and note["severity"] == "critical" for note in notifications)

    asyncio.run(_run())
