"""Legacy single-queue Redis worker — deprecated; use platform.events.queues.queue_manager."""
from __future__ import annotations

import json
from dataclasses import dataclass

import redis
from redis.exceptions import RedisError

from app.core.config import DEV_ORG_ID, settings
from app.services.event_queue import event_queue
from app.services.metrics import metrics_store
from app.services.principal_context import build_principal


@dataclass
class RedisQueueResult:
    status: str
    detail: str | None = None
    payload: dict | None = None


class RedisQueueService:
    def __init__(self) -> None:
        self.client: redis.Redis | None = None
        redis_url = settings.redis_url.strip()
        if redis_url:
            self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.main_queue = settings.queue_main_name
        self.dlq_queue = settings.queue_dlq_name
        self.processed_ttl_seconds = 24 * 3600

    def enqueue(self, idempotency_key: str, payload: dict) -> RedisQueueResult:
        if self.client is None:
            return RedisQueueResult(status="skipped", detail="redis_unconfigured")
        message = {"idempotency_key": idempotency_key, "payload": payload, "attempts": 0}
        try:
            self.client.rpush(self.main_queue, json.dumps(message))
            event_type = str(payload.get("event_type", "policy.queue.enqueued"))
            principal = payload.get("principal")
            if not isinstance(principal, dict) or not principal.get("roles"):
                principal = build_principal(user_id="api.queue", roles=["system_worker"], attrs={})
            envelope = {
                "event_id": idempotency_key or f"legacy-{abs(hash(json.dumps(payload, sort_keys=True)))}",
                "event_type": event_type,
                "org_id": str(payload.get("org_id", DEV_ORG_ID)),
                "source": "api.queue",
                "occurred_at": str(payload.get("occurred_at", "")),
                "trace_id": str(payload.get("trace_id", idempotency_key)),
                "principal": principal,
                "payload": payload,
                "schema_version": "v1",
            }
            event_queue.publish(envelope)
            return RedisQueueResult(status="queued", payload=message)
        except RedisError as exc:
            return RedisQueueResult(status="error", detail=str(exc))

    def process_next(self, max_attempts: int = 3) -> RedisQueueResult:
        if self.client is None:
            return RedisQueueResult(status="skipped", detail="redis_unconfigured")
        try:
            raw = self.client.lpop(self.main_queue)
        except RedisError as exc:
            return RedisQueueResult(status="error", detail=str(exc))

        if raw is None:
            return RedisQueueResult(status="empty")

        message = json.loads(raw)
        idempotency_key = str(message.get("idempotency_key", ""))
        if idempotency_key and self.client.get(f"{self.main_queue}:processed:{idempotency_key}"):
            return RedisQueueResult(status="deduped", payload=message)

        message["attempts"] = int(message.get("attempts", 0)) + 1
        should_fail = bool(message.get("payload", {}).get("force_fail"))
        if should_fail and message["attempts"] < max_attempts:
            self.client.rpush(self.main_queue, json.dumps(message))
            metrics_store.incr_queue_retry()
            return RedisQueueResult(status="retry", payload=message)

        if should_fail:
            self.client.rpush(self.dlq_queue, json.dumps(message))
            metrics_store.incr_queue_dlq()
            return RedisQueueResult(status="dlq", payload=message)

        if idempotency_key:
            self.client.setex(
                f"{self.main_queue}:processed:{idempotency_key}",
                self.processed_ttl_seconds,
                "1",
            )
        return RedisQueueResult(status="processed", payload=message)


redis_queue_service = RedisQueueService()
