import json
from dataclasses import dataclass

import redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.services.event_topology import queue_dlq_name, route_for_envelope
from app.services.metrics import metrics_store


@dataclass
class EventQueueResult:
    status: str
    queue: str | None = None
    detail: str | None = None
    envelope: dict | None = None
    idempotent_replay: bool = False


class EventQueue:
    def __init__(self) -> None:
        self.client: redis.Redis | None = None
        redis_url = settings.redis_url.strip()
        if not redis_url:
            if settings.app_env.lower() != "dev":
                raise RuntimeError("REDIS_URL is required outside dev")
            return
        if settings.redis_require_tls and not redis_url.lower().startswith("rediss://"):
            raise RuntimeError("REDIS_REQUIRE_TLS=true requires REDIS_URL to use rediss://")
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)

    def publish(self, envelope: dict) -> EventQueueResult:
        from app.modules.platform.events.queues.queue_manager import queue_manager

        result = queue_manager.publish(envelope)
        return EventQueueResult(
            status=result.status,
            queue=result.queue,
            detail=result.detail,
            envelope=result.envelope,
        )

    def process_next(self, queue: str, max_attempts: int = 3) -> EventQueueResult:
        if self.client is None:
            return EventQueueResult(status="skipped", queue=queue, detail="redis_unconfigured")
        try:
            processing_queue = f"{queue}:processing"
            raw = self.client.brpoplpush(queue, processing_queue, timeout=1)
        except RedisError as exc:
            return EventQueueResult(status="error", queue=queue, detail=str(exc))
        if raw is None:
            return EventQueueResult(status="empty", queue=queue)
        envelope = json.loads(raw)
        event_id = str(envelope.get("event_id", "")).strip()
        if event_id:
            dedupe_key = f"{queue}:processed:{event_id}"
            if self.client.get(dedupe_key):
                return EventQueueResult(status="deduped", queue=queue, envelope=envelope, idempotent_replay=True)
        attempts = int(envelope.get("_attempts", 0)) + 1
        envelope["_attempts"] = attempts
        should_fail = bool(envelope.get("payload", {}).get("force_fail"))
        if should_fail and attempts < max_attempts:
            self.client.lrem(processing_queue, 1, raw)
            self.client.rpush(queue, json.dumps(envelope))
            metrics_store.incr_queue_retry()
            return EventQueueResult(status="retry", queue=queue, envelope=envelope)
        if should_fail:
            self.client.lrem(processing_queue, 1, raw)
            self.client.rpush(queue_dlq_name(queue), json.dumps(envelope))
            metrics_store.incr_queue_dlq()
            return EventQueueResult(status="dlq", queue=queue_dlq_name(queue), envelope=envelope)
        if event_id:
            self.client.setex(dedupe_key, 24 * 3600, "1")
        self.client.lrem(processing_queue, 1, raw)
        return EventQueueResult(status="processed", queue=queue, envelope=envelope)

    def lag(self, queue: str) -> int:
        if self.client is None:
            return 0
        try:
            return int(self.client.llen(queue))
        except RedisError:
            return -1


event_queue = EventQueue()
