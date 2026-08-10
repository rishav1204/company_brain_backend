"""Context retrieval cache using existing redis_cache helpers (Wave 4)."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services.cache.redis_cache import get_cached, set_cached
from app.services.logger import log_event

NAMESPACE = "m38.context.retrieval"


class ContextCache:
    def enabled(self) -> bool:
        return bool(getattr(settings, "m38_context_cache_enabled", True))

    def get(
        self,
        org_id: str,
        *,
        plan_sig: str,
        entity_key: str,
        query: str,
    ) -> dict | None:
        if not self.enabled():
            return None
        hit = get_cached(
            org_id,
            NAMESPACE,
            {"plan": plan_sig, "entity": entity_key, "q": (query or "")[:200]},
        )
        if hit:
            log_event("m38.context.cache_hit", org_id=org_id, plan=plan_sig[:80])
            return hit if isinstance(hit, dict) else None
        return None

    def set(
        self,
        org_id: str,
        *,
        plan_sig: str,
        entity_key: str,
        query: str,
        payload: dict[str, Any],
    ) -> None:
        if not self.enabled():
            return
        ttl = int(getattr(settings, "m38_context_cache_ttl_seconds", 45) or 45)
        set_cached(
            org_id,
            NAMESPACE,
            payload,
            {"plan": plan_sig, "entity": entity_key, "q": (query or "")[:200]},
            ttl=ttl,
        )


context_cache = ContextCache()
