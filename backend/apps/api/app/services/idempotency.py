import redis
from redis.exceptions import RedisError

from app.core.config import settings


class IdempotencyService:
    def __init__(self) -> None:
        self.client: redis.Redis | None = None
        redis_url = settings.redis_url.strip()
        if redis_url:
            self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.prefix = "idempotency:workflow"

    def is_replay(self, workflow_id: str, key: str) -> bool:
        if not key or self.client is None:
            return False
        redis_key = f"{self.prefix}:{workflow_id}:{key}"
        try:
            return bool(self.client.exists(redis_key))
        except RedisError:
            return False

    def mark(self, workflow_id: str, key: str, ttl_seconds: int = 86400) -> None:
        if not key or self.client is None:
            return
        redis_key = f"{self.prefix}:{workflow_id}:{key}"
        try:
            self.client.set(redis_key, "1", ex=ttl_seconds, nx=True)
        except RedisError:
            return


idempotency_service = IdempotencyService()
