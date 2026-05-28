from __future__ import annotations

import time

from app.core.config import settings


class EventRateLimitService:
    def __init__(self) -> None:
        self._memory: dict[str, list[float]] = {}

    def _redis_client(self):
        try:
            import redis

            url = settings.redis_url.strip()
            if not url:
                return None
            return redis.Redis.from_url(url, decode_responses=True)
        except Exception:
            return None

    def allow_publish(self, org_id: str) -> tuple[bool, str | None]:
        limit = settings.event_publish_rate_limit_per_minute
        if limit <= 0:
            return True, None
        key = f"events:rate:publish:{org_id}"
        client = self._redis_client()
        now = time.time()
        window_start = now - 60
        if client:
            try:
                pipe = client.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, 120)
                results = pipe.execute()
                count = int(results[2])
                if count > limit:
                    return False, f"publish rate limit exceeded ({limit}/min)"
                return True, None
            except Exception:
                pass
        bucket = self._memory.setdefault(key, [])
        bucket[:] = [t for t in bucket if t > window_start]
        bucket.append(now)
        if len(bucket) > limit:
            return False, f"publish rate limit exceeded ({limit}/min)"
        return True, None


event_rate_limit_service = EventRateLimitService()
