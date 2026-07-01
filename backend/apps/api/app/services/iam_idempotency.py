from redis.exceptions import RedisError

from app.services.redis_client import get_redis_client


class IamIdempotencyService:
    def __init__(self) -> None:
        self.prefix = "idempotency:iam"
        self.client = get_redis_client()

    def _key(self, scope: str, org_id: str, idempotency_key: str) -> str:
        return f"{self.prefix}:{scope}:{org_id}:{idempotency_key}"

    def is_replay(self, scope: str, org_id: str, idempotency_key: str | None) -> bool:
        if not idempotency_key or not self.client:
            return False
        try:
            return bool(self.client.exists(self._key(scope, org_id, idempotency_key)))
        except RedisError:
            return False

    def mark(self, scope: str, org_id: str, idempotency_key: str | None, ttl_seconds: int = 86400) -> None:
        if not idempotency_key or not self.client:
            return
        try:
            self.client.set(self._key(scope, org_id, idempotency_key), "1", ex=ttl_seconds, nx=True)
        except RedisError:
            pass


iam_idempotency_service = IamIdempotencyService()
