from __future__ import annotations

import json
from dataclasses import dataclass

import redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.modules.platform.events.services.retry_service import is_ready_for_retry, schedule_retry, should_retry
from app.services.event_topology import queue_dlq_name, route_for_envelope
from app.services.metrics import metrics_store
from app.services.redis_client import get_redis_client

CONSUMER_DEDUP_TTL_SECONDS = 7 * 24 * 3600


@dataclass
class QueuePublishResult:
    status: str
    queue: str | None = None
    detail: str | None = None
    envelope: dict | None = None
    idempotent_replay: bool = False


@dataclass
class QueueClaimResult:
    status: str
    queue: str
    envelope: dict | None = None
    claim_token: str | None = None
    detail: str | None = None
    idempotent_replay: bool = False


class QueueManager:
    """Redis Streams primary backend with list-queue fallback."""

    def __init__(self) -> None:
        self.client: redis.Redis | None = get_redis_client()
        self.use_streams = settings.event_queue_backend.lower() == "redis_streams"

    def _stream_key(self, queue: str) -> str:
        return f"stream:{queue}"

    def _consumer_group(self, queue: str) -> str:
        return f"{queue}:workers"

    def _ensure_group(self, queue: str) -> None:
        if self.client is None:
            return
        stream = self._stream_key(queue)
        group = self._consumer_group(queue)
        try:
            self.client.xgroup_create(stream, group, id="0", mkstream=True)
        except RedisError as exc:
            if "BUSYGROUP" not in str(exc):
                pass

    def publish(self, envelope: dict, *, priority: str = "normal") -> QueuePublishResult:
        queue = route_for_envelope(envelope)
        if priority == "high":
            from app.modules.platform.events.queues.priority_queue import apply_priority_route

            queue = apply_priority_route(queue)
        if self.client is None:
            return QueuePublishResult(status="skipped", queue=queue, detail="redis_unconfigured", envelope=envelope)
        payload = json.dumps(envelope)
        try:
            if self.use_streams:
                self._ensure_group(queue)
                self.client.xadd(
                    self._stream_key(queue),
                    {"data": payload},
                    maxlen=settings.redis_stream_maxlen,
                    approximate=True,
                )
            else:
                self.client.rpush(queue, payload)
            metrics_store.incr_event_published()
            return QueuePublishResult(status="queued", queue=queue, envelope=envelope)
        except RedisError as exc:
            return QueuePublishResult(status="error", queue=queue, detail=str(exc), envelope=envelope)

    def claim_next(self, queue: str, consumer_name: str = "worker-1") -> QueueClaimResult:
        if self.client is None:
            return QueueClaimResult(status="skipped", queue=queue, detail="redis_unconfigured")
        if self.use_streams:
            return self._claim_stream(queue, consumer_name)
        return self._claim_list(queue)

    def _claim_list(self, queue: str) -> QueueClaimResult:
        assert self.client is not None
        processing_queue = f"{queue}:processing"
        try:
            raw = self.client.brpoplpush(queue, processing_queue, timeout=1)
        except RedisError as exc:
            return QueueClaimResult(status="error", queue=queue, detail=str(exc))
        if raw is None:
            return QueueClaimResult(status="empty", queue=queue)
        envelope = json.loads(raw)
        event_id = str(envelope.get("event_id", "")).strip()
        if event_id:
            dedupe_key = f"{queue}:processed:{event_id}"
            if self.client.get(dedupe_key):
                self.client.lrem(processing_queue, 1, raw)
                return QueueClaimResult(status="deduped", queue=queue, envelope=envelope, idempotent_replay=True)
        if not is_ready_for_retry(envelope):
            self.client.lrem(processing_queue, 1, raw)
            self.client.lpush(queue, raw)
            return QueueClaimResult(
                status="delayed", queue=queue, envelope=envelope, detail="retry_not_due", claim_token=raw
            )
        return QueueClaimResult(status="claimed", queue=queue, envelope=envelope, claim_token=raw)

    def _claim_stream(self, queue: str, consumer_name: str) -> QueueClaimResult:
        assert self.client is not None
        stream = self._stream_key(queue)
        group = self._consumer_group(queue)
        self._ensure_group(queue)
        self.reclaim_stale(queue, consumer_name)
        try:
            messages = self.client.xreadgroup(
                groupname=group,
                consumername=consumer_name,
                streams={stream: ">"},
                count=1,
                block=1000,
            )
        except RedisError as exc:
            return QueueClaimResult(status="error", queue=queue, detail=str(exc))
        if not messages:
            return QueueClaimResult(status="empty", queue=queue)
        _, entries = messages[0]
        msg_id, fields = entries[0]
        raw = fields.get("data") or "{}"
        envelope = json.loads(raw)
        event_id = str(envelope.get("event_id", "")).strip()
        if event_id:
            dedupe_key = f"{queue}:processed:{event_id}"
            if self.client.get(dedupe_key):
                self.client.xack(stream, group, msg_id)
                return QueueClaimResult(status="deduped", queue=queue, envelope=envelope, idempotent_replay=True)
        if not is_ready_for_retry(envelope):
            return QueueClaimResult(status="delayed", queue=queue, envelope=envelope, detail="retry_not_due")
        return QueueClaimResult(status="claimed", queue=queue, envelope=envelope, claim_token=msg_id)

    def complete_claim(self, queue: str, envelope: dict, claim_token: str | None) -> None:
        if self.client is None:
            return
        event_id = str(envelope.get("event_id", "")).strip()
        if self.use_streams and claim_token:
            stream = self._stream_key(queue)
            group = self._consumer_group(queue)
            self.client.xack(stream, group, claim_token)
        elif claim_token:
            processing_queue = f"{queue}:processing"
            self.client.lrem(processing_queue, 1, claim_token)
        if event_id:
            self.client.setex(f"{queue}:processed:{event_id}", CONSUMER_DEDUP_TTL_SECONDS, "1")
        metrics_store.incr_event_processed()

    def fail_claim(self, queue: str, envelope: dict, claim_token: str | None, error: str) -> QueuePublishResult:
        """Requeue with backoff or move to DLQ after consumer failure."""
        if envelope is None:
            return QueuePublishResult(status="error", queue=queue, detail="no envelope")
        envelope["_last_error"] = error[:500]
        envelope = schedule_retry(envelope)
        attempts = int(envelope.get("_attempts", 0))
        force_fail = bool((envelope.get("payload") or {}).get("force_fail"))
        retryable = force_fail or True

        if retryable and should_retry(attempts):
            self._release_claim_for_retry(queue, envelope, claim_token)
            metrics_store.incr_queue_retry()
            self._audit_retry_attempt(envelope, queue, attempts, error)
            self.publish(envelope)
            return QueuePublishResult(status="retry", queue=queue, envelope=envelope, detail=error)

        dlq = queue_dlq_name(queue)
        self._move_to_dlq(queue, envelope, claim_token)
        metrics_store.incr_queue_dlq()
        self._emit_system_failure(envelope, queue, error)
        return QueuePublishResult(status="dlq", queue=dlq, envelope=envelope, detail=error)

    def _release_claim_for_retry(self, queue: str, envelope: dict, claim_token: str | None) -> None:
        if self.client is None:
            return
        if self.use_streams and claim_token:
            stream = self._stream_key(queue)
            group = self._consumer_group(queue)
            self.client.xack(stream, group, claim_token)
        elif claim_token:
            processing_queue = f"{queue}:processing"
            self.client.lrem(processing_queue, 1, claim_token)

    def _move_to_dlq(self, queue: str, envelope: dict, claim_token: str | None) -> None:
        if self.client is None:
            return
        dlq = queue_dlq_name(queue)
        payload = json.dumps(envelope)
        if self.use_streams:
            self._release_claim_for_retry(queue, envelope, claim_token)
            self.client.xadd(
                self._stream_key(dlq),
                {"data": payload},
                maxlen=settings.redis_stream_maxlen,
                approximate=True,
            )
        else:
            if claim_token:
                processing_queue = f"{queue}:processing"
                self.client.lrem(processing_queue, 1, claim_token)
            self.client.rpush(dlq, payload)

    def _audit_retry_attempt(self, envelope: dict, queue: str, attempts: int, error: str) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            org_id = str(envelope.get("org_id", ""))
            if not org_id:
                return
            audit_service.record(
                org_id=org_id,
                actor_type="system",
                actor_id="platform.queue",
                action="queue.retry.scheduled",
                object_ref=f"queue:{queue}:event:{envelope.get('event_id', '')}",
                payload={"attempt": attempts, "error": error[:200], "queue": queue},
                trace_id=str(envelope.get("trace_id", "")) or None,
                source_service="platform.queue",
            )
        except Exception:
            pass

    def _emit_system_failure(self, envelope: dict, queue: str, error: str) -> None:
        try:
            from app.modules.platform.events.events.system_events import emit_job_failed, emit_retry_exceeded

            org_id = str(envelope.get("org_id", ""))
            if not org_id:
                return
            attempts = int(envelope.get("_attempts", 0))
            emit_job_failed(org_id, queue=queue, event_id=str(envelope.get("event_id", "")), error=error)
            if attempts >= settings.event_retry_max_attempts:
                emit_retry_exceeded(org_id, queue=queue, event_id=str(envelope.get("event_id", "")))
            try:
                from app.modules.platform.governance.services.audit_service import audit_service

                audit_service.record(
                    org_id=org_id,
                    actor_type="system",
                    actor_id="platform.queue",
                    action="queue.job.failed",
                    object_ref=f"queue:{queue}:event:{envelope.get('event_id', '')}",
                    payload={"error": error[:500], "attempts": attempts, "queue": queue},
                    trace_id=str(envelope.get("trace_id", "")) or None,
                    source_service="platform.queue",
                )
            except Exception:
                pass
        except Exception:
            pass

    def process_next(self, queue: str, consumer_name: str = "worker-1") -> QueuePublishResult:
        """Legacy: claim and return as processed without running consumer (tests only)."""
        claim = self.claim_next(queue, consumer_name)
        if claim.status != "claimed" or not claim.envelope:
            return QueuePublishResult(
                status=claim.status,
                queue=queue,
                detail=claim.detail,
                envelope=claim.envelope,
                idempotent_replay=claim.idempotent_replay,
            )
        envelope = claim.envelope
        force_fail = bool((envelope.get("payload") or {}).get("force_fail"))
        if force_fail:
            return self.fail_claim(queue, envelope, claim.claim_token, "force_fail")
        self.complete_claim(queue, envelope, claim.claim_token)
        return QueuePublishResult(status="processed", queue=queue, envelope=envelope)

    def reclaim_stale(self, queue: str, consumer_name: str) -> int:
        if self.client is None or not self.use_streams:
            return 0
        stream = self._stream_key(queue)
        group = self._consumer_group(queue)
        min_idle_ms = settings.event_queue_inflight_seconds * 1000
        try:
            pending = self.client.xautoclaim(stream, group, consumer_name, min_idle_time=min_idle_ms, start_id="0-0", count=10)
            return len(pending[1]) if pending and len(pending) > 1 else 0
        except RedisError:
            return 0

    def lag(self, queue: str) -> int:
        if self.client is None:
            return 0
        try:
            if self.use_streams:
                return int(self.client.xlen(self._stream_key(queue)))
            return int(self.client.llen(queue))
        except RedisError:
            return -1

    def dlq_lag(self, queue: str) -> int:
        return self.lag(queue_dlq_name(queue))


queue_manager = QueueManager()
