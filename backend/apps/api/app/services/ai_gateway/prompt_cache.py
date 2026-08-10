"""Prompt / entity context cache via existing redis_cache (Wave 6)."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.services.cache.redis_cache import get_cached, set_cached
from app.services.logger import log_event

NS_PROMPT = "ai.gateway.prompt"
NS_ENTITY = "ai.gateway.entity"
NS_SUMMARY = "ai.gateway.summary"


class GatewayCache:
    def enabled(self) -> bool:
        return bool(getattr(settings, "ai_prompt_cache_enabled", True))

    def get_prompt_response(
        self,
        org_id: str,
        *,
        fingerprint: str,
        model: str,
        execution_class: str,
    ) -> dict | None:
        if not self.enabled():
            return None
        hit = get_cached(
            org_id,
            NS_PROMPT,
            {"fp": fingerprint, "model": model, "ec": execution_class},
        )
        if hit:
            log_event("ai.gateway.cache_hit", org_id=org_id, kind="prompt", model=model)
            return hit if isinstance(hit, dict) else None
        return None

    def set_prompt_response(
        self,
        org_id: str,
        *,
        fingerprint: str,
        model: str,
        execution_class: str,
        payload: dict[str, Any],
    ) -> None:
        if not self.enabled():
            return
        ttl = int(getattr(settings, "ai_prompt_cache_ttl_seconds", 120) or 120)
        set_cached(
            org_id,
            NS_PROMPT,
            payload,
            {"fp": fingerprint, "model": model, "ec": execution_class},
            ttl=ttl,
        )

    def get_entity_context(self, org_id: str, *, entity_type: str, entity_id: str, version: str = "v1") -> dict | None:
        if not self.enabled():
            return None
        return get_cached(org_id, NS_ENTITY, {"t": entity_type, "id": entity_id, "v": version})

    def set_entity_context(
        self,
        org_id: str,
        *,
        entity_type: str,
        entity_id: str,
        payload: dict,
        version: str = "v1",
        ttl: int | None = None,
    ) -> None:
        if not self.enabled():
            return
        set_cached(
            org_id,
            NS_ENTITY,
            payload,
            {"t": entity_type, "id": entity_id, "v": version},
            ttl=ttl or int(getattr(settings, "ai_entity_cache_ttl_seconds", 60) or 60),
        )

    def invalidate_entity(self, org_id: str, *, entity_type: str, entity_id: str) -> None:
        from app.services.cache.redis_cache import invalidate_key

        invalidate_key(org_id, NS_ENTITY, {"t": entity_type, "id": entity_id, "v": "v1"})


gateway_cache = GatewayCache()
