from __future__ import annotations

import time

import redis

from app.core.config import settings


class IntegrationsRateLimitService:
    def allow_api_key(self, *, org_id: str, api_key_id: str) -> bool:
        """
        Best-effort per-minute rate limit for Module 7 API keys.
        Uses Redis if configured; otherwise allow (dev-friendly).
        """
        limit = int(settings.integrations_api_key_rate_limit_per_minute or 120)
        if limit <= 0:
            return True
        redis_url = (settings.redis_url or "").strip()
        if not redis_url:
            return True
        if settings.redis_require_tls and not redis_url.lower().startswith("rediss://"):
            return True
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        window = int(time.time() // 60)
        key = f"ratelimit:integrations:api_key:{org_id}:{api_key_id}:{window}"
        try:
            count = int(client.incr(key))
            if count == 1:
                client.expire(key, 90)
            return count <= limit
        except Exception:
            return True


integrations_rate_limit_service = IntegrationsRateLimitService()

