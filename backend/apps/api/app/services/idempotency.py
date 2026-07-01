from redis.exceptions import RedisError

from app.services.redis_client import get_redis_client


class IdempotencyService:
    def __init__(self) -> None:
        self.client = get_redis_client()
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
