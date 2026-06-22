from __future__ import annotations

import redis

from app.core.config import settings


class GatewayRateLimitService:
    def __init__(self) -> None:
        self._redis: redis.Redis | None = None
        if settings.redis_url:
            try:
                self._redis = redis.from_url(settings.redis_url, decode_responses=True)
            except Exception:
                self._redis = None
        self._memory: dict[str, tuple[int, float]] = {}

    def allow(
        self,
        *,
        org_id: str,
        api_key_id: str,
        per_minute: int = 100,
        per_hour: int = 1000,
    ) -> bool:
        minute_key = f"gw:rl:min:{org_id}:{api_key_id}"
        hour_key = f"gw:rl:hr:{org_id}:{api_key_id}"
        if self._redis:
            try:
                minute_count = int(self._redis.incr(minute_key))
                if minute_count == 1:
                    self._redis.expire(minute_key, 60)
                if minute_count > per_minute:
                    return False
                hour_count = int(self._redis.incr(hour_key))
                if hour_count == 1:
                    self._redis.expire(hour_key, 3600)
                return hour_count <= per_hour
            except Exception:
                pass
        return True


gateway_rate_limit_service = GatewayRateLimitService()
