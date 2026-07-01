from app.core.config import settings
from app.services.redis_client import get_redis_client


class IntegrationsRateLimitService:
    def allow_api_key(self, *, org_id: str, api_key_id: str) -> bool:
        """
        Best-effort per-minute rate limit for Module 7 API keys.
        Uses Redis if configured; otherwise allow (dev-friendly).
        """
        limit = int(settings.integrations_api_key_rate_limit_per_minute or 120)
        if limit <= 0:
            return True
        client = get_redis_client()
        if not client:
            return True
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

