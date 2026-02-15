"""Contract tests for CONV-02 multi-turn conversation context memory."""

from __future__ import annotations

import asyncio

from src.platform_api.schemas_v1 import RequestContext
from src.platform_api.schemas_v2 import CreateConversationSessionRequest, CreateConversationTurnRequest
from src.platform_api.services.conversation_service import ConversationService
from src.platform_api.state_store import InMemoryStateStore


def _context(*, user_id: str = "user-a") -> RequestContext:
    return RequestContext(
        request_id="req-conv-memory-001",
        tenant_id="tenant-a",
        user_id=user_id,
    )


def test_context_memory_links_artifacts_across_turns() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        service = ConversationService(store=store)
        context = _context(user_id="user-a")

        session = await service.create_session(
            request=CreateConversationSessionRequest(channel="openclaw", topic="execution"),
            context=context,
        )
        session_id = session.session.id

        await service.create_turn(
            session_id=session_id,
            request=CreateConversationTurnRequest(
                role="user",
                message="deploy strat-001 on dep-001 and watch portfolio-paper-001",
            ),
            context=context,
        )
        await service.create_turn(
            session_id=session_id,
            request=CreateConversationTurnRequest(
                role="user",
                message="place a buy order for BTCUSDT",
            ),
            context=context,
        )

        refreshed = await service.get_session(session_id=session_id, context=context)
        memory = refreshed.session.metadata["contextMemory"]
        assert memory["lastIntent"] == "order"
        assert "strat-001" in memory["linkedArtifacts"]["strategyIds"]
        assert "dep-001" in memory["linkedArtifacts"]["deploymentIds"]
        assert "portfolio-paper-001" in memory["linkedArtifacts"]["portfolioIds"]
        assert "BTCUSDT" in memory["symbols"]
        assert memory["turnCount"] == 2

    asyncio.run(_run())


def test_context_memory_applies_recent_message_retention_limit() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        service = ConversationService(store=store)
        context = _context(user_id="user-a")

        session = await service.create_session(
            request=CreateConversationSessionRequest(channel="web", topic="retention"),
            context=context,
        )
        session_id = session.session.id

        for idx in range(7):
            await service.create_turn(
                session_id=session_id,
                request=CreateConversationTurnRequest(role="user", message=f"turn {idx}"),
                context=context,
            )

        refreshed = await service.get_session(session_id=session_id, context=context)
        memory = refreshed.session.metadata["contextMemory"]
        recent_messages = memory["recentMessages"]
        assert len(recent_messages) == 5
        assert recent_messages[0]["message"] == "turn 2"
        assert recent_messages[-1]["message"] == "turn 6"

    asyncio.run(_run())


def test_context_memory_isolated_per_user() -> None:
    async def _run() -> None:
        store = InMemoryStateStore()
        service = ConversationService(store=store)

        user_a = _context(user_id="user-a")
        user_b = _context(user_id="user-b")

        session_a = await service.create_session(
            request=CreateConversationSessionRequest(channel="cli", topic="user-a"),
            context=user_a,
        )
        session_b = await service.create_session(
            request=CreateConversationSessionRequest(channel="cli", topic="user-b"),
            context=user_b,
        )

        await service.create_turn(
            session_id=session_a.session.id,
            request=CreateConversationTurnRequest(role="user", message="deploy strat-001"),
            context=user_a,
        )
        await service.create_turn(
            session_id=session_b.session.id,
            request=CreateConversationTurnRequest(role="user", message="deploy strat-002"),
            context=user_b,
        )

        refreshed_a = await service.get_session(session_id=session_a.session.id, context=user_a)
        refreshed_b = await service.get_session(session_id=session_b.session.id, context=user_b)
        memory_a = refreshed_a.session.metadata["contextMemory"]
        memory_b = refreshed_b.session.metadata["contextMemory"]

        assert "strat-001" in memory_a["linkedArtifacts"]["strategyIds"]
        assert "strat-002" not in memory_a["linkedArtifacts"]["strategyIds"]
        assert "strat-002" in memory_b["linkedArtifacts"]["strategyIds"]
        assert "strat-001" not in memory_b["linkedArtifacts"]["strategyIds"]

    asyncio.run(_run())
