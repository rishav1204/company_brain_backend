from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import ResolvedEntity
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState


def _screen_entity_id(world_state: WorldState | None) -> str | None:
    if world_state and world_state.screen:
        return world_state.screen.entity_id
    return None


class ContextRanker:
    def rank_memory(
        self,
        items: list[dict],
        *,
        query: str,
        world_state: WorldState | None = None,
        entities: list[ResolvedEntity] | None = None,
        top_k: int = 10,
    ) -> list[dict]:
        if not items:
            return []
        screen_id = _screen_entity_id(world_state)
        entity_ids = {e.entity_id for e in (entities or []) if e.entity_id}

        def score(item: dict) -> float:
            base = float(item.get("final_score") or item.get("importance_score") or 0.5)
            if screen_id and str(item.get("entity_id") or "") == screen_id:
                base += 0.3
            if entity_ids and str(item.get("entity_id") or "") in entity_ids:
                base += 0.2
            content = str(item.get("content") or item.get("title") or "").lower()
            q = query.lower()
            for token in q.split()[:6]:
                if len(token) > 3 and token in content:
                    base += 0.05
            return base

        ranked = sorted(items, key=score, reverse=True)
        deduped: dict[str, dict] = {}
        for item in ranked:
            key = str(item.get("id") or item.get("content", "")[:60])
            if key not in deduped:
                deduped[key] = item
        return list(deduped.values())[:top_k]

    def rank_documents(self, items: list[dict], *, top_k: int = 5) -> list[dict]:
        if not items:
            return []
        return items[:top_k]

    def rank_graph(self, items: list[dict], *, top_k: int = 5) -> list[dict]:
        if not items:
            return []
        return items[:top_k]


context_ranker = ContextRanker()
