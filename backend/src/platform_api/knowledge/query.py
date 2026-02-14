"""Knowledge Base query service for /v2 retrieval endpoints."""

from __future__ import annotations

from src.platform_api.knowledge.models import KnowledgePatternRecord, LessonLearnedRecord, MarketRegimeRecord
from src.platform_api.state_store import InMemoryStateStore


class KnowledgeQueryService:
    """Simple hybrid-ish retrieval over in-memory KB records."""

    def __init__(self, store: InMemoryStateStore) -> None:
        self._store = store

    def search(
        self,
        *,
        query: str,
        assets: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        normalized_query = query.lower().strip()
        asset_filter = {asset.upper() for asset in assets or []}
        scored: list[tuple[int, dict[str, object]]] = []

        for pattern in self._store.knowledge_patterns.values():
            haystack = " ".join(
                [pattern.name, pattern.description, pattern.pattern_type, " ".join(pattern.suitable_regimes)]
            ).lower()
            if normalized_query not in haystack:
                continue
            if asset_filter and not asset_filter.intersection({a.upper() for a in pattern.assets}):
                continue
            score = 100 - len(haystack.replace(normalized_query, "", 1))
            scored.append(
                (
                    score,
                    {
                        "kind": "pattern",
                        "id": pattern.id,
                        "title": pattern.name,
                        "summary": pattern.description,
                        "score": float(max(score, 1)),
                        "evidence": {"assets": pattern.assets, "regimes": pattern.suitable_regimes},
                    },
                )
            )

        for lesson in self._store.lessons_learned.values():
            if normalized_query and normalized_query not in lesson.lesson.lower():
                continue
            score = 40
            scored.append(
                (
                    score,
                    {
                        "kind": "lesson",
                        "id": lesson.id,
                        "title": lesson.category,
                        "summary": lesson.lesson,
                        "score": float(score),
                        "evidence": {"tags": lesson.tags, "strategyId": lesson.strategy_id},
                    },
                )
            )

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in scored[: max(1, limit)]]

    def list_patterns(
        self,
        *,
        pattern_type: str | None = None,
        asset: str | None = None,
        limit: int = 25,
    ) -> list[KnowledgePatternRecord]:
        items = list(self._store.knowledge_patterns.values())
        if pattern_type:
            items = [item for item in items if item.pattern_type == pattern_type]
        if asset:
            needle = asset.upper()
            items = [item for item in items if needle in {entry.upper() for entry in item.assets}]
        return items[: max(1, limit)]

    def get_regime(self, *, asset: str) -> MarketRegimeRecord | None:
        needle = asset.upper()
        for regime in self._store.market_regimes.values():
            if regime.asset.upper() == needle and regime.end_at is None:
                return regime
        return None

    def recent_lessons(self, *, limit: int = 5) -> list[LessonLearnedRecord]:
        lessons = list(self._store.lessons_learned.values())
        lessons.sort(key=lambda item: item.created_at, reverse=True)
        return lessons[: max(1, limit)]
