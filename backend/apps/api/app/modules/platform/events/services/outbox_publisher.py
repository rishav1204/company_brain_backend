from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass

from app.core.config import settings
from app.modules.platform.events.repositories.outbox_repository import outbox_repository
from app.modules.platform.events.services.retry_service import next_retry_at
from app.services.logger import log_event
from app.services.redis_client import get_redis_client


_IDEMPOTENT_XADD_LUA = """
local key = KEYS[1]
local stream = KEYS[2]
local token = ARGV[1]
local ttl = tonumber(ARGV[2])
local data = ARGV[3]
local maxlen = tonumber(ARGV[4])
local approx = tonumber(ARGV[5])

if redis.call("set", key, token, "NX", "EX", ttl) == false then
  return "deduped"
end

if approx == 1 then
  return redis.call("xadd", stream, "MAXLEN", "~", maxlen, "*", "data", data)
else
  return redis.call("xadd", stream, "MAXLEN", maxlen, "*", "data", data)
end
"""


@dataclass(frozen=True)
class PublishSummary:
    claimed: int
    published: int
    failed: int
    deduped: int
    dead: int = 0


def _publisher_id() -> str:
    return f"outbox-publisher:{socket.gethostname()}:{int(time.time())}"


def _financial_queues() -> set[str]:
    return {
        settings.queue_workflow_execution,
        settings.queue_workflow_approvals,
        settings.queue_integration_bank,
        settings.queue_integration_gst,
    }


class OutboxPublisher:
    def publish_once(self, *, limit: int = 100) -> PublishSummary:
        if not outbox_repository.schema_ready():
            return PublishSummary(claimed=0, published=0, failed=0, deduped=0, dead=0)
        client = get_redis_client()
        if client is None:
            if settings.app_env.lower() == "prod":
                raise RuntimeError("Redis required for outbox publishing in production")
            return PublishSummary(claimed=0, published=0, failed=0, deduped=0, dead=0)

        pub_id = _publisher_id()
        batch = int(limit or getattr(settings, "outbox_publish_batch_size", 100) or 100)
        rows = outbox_repository.claim_batch(publisher_id=pub_id, limit=batch, lock_seconds=30)
        published = failed = deduped = dead = 0
        fin = _financial_queues()
        for row in rows:
            try:
                envelope = row.envelope or {}
                queue_name = row.queue_name
                stream = f"stream:{queue_name}"
                data = json.dumps(envelope, separators=(",", ":"), default=str)
                idem_key = f"outbox:published:{row.org_id}:{row.event_id}"
                ttl = int(getattr(settings, "outbox_publish_dedupe_ttl_seconds", 30 * 24 * 3600))
                maxlen = int(getattr(settings, "redis_stream_financial_maxlen", settings.redis_stream_maxlen))
                approx = 0 if queue_name in fin else 1
                if queue_name not in fin:
                    maxlen = int(settings.redis_stream_maxlen)
                result = client.eval(
                    _IDEMPOTENT_XADD_LUA,
                    2,
                    idem_key,
                    stream,
                    pub_id,
                    ttl,
                    data,
                    maxlen,
                    approx,
                )
                if str(result) == "deduped":
                    deduped += 1
                    outbox_repository.mark_published(org_id=row.org_id, outbox_id=row.id, redis_stream_id=None)
                else:
                    published += 1
                    outbox_repository.mark_published(org_id=row.org_id, outbox_id=row.id, redis_stream_id=str(result))
                try:
                    from app.services.metrics import metrics_store

                    metrics_store.incr_outbox_published()
                except Exception:
                    pass
            except Exception as exc:
                failed += 1
                try:
                    status = outbox_repository.mark_failed(
                        org_id=row.org_id,
                        outbox_id=row.id,
                        error=str(exc),
                        next_attempt_at=next_retry_at(row.attempt_count + 1),
                        attempt_count=row.attempt_count,
                        failure_class="publish_error",
                    )
                    if status == "dead":
                        dead += 1
                        try:
                            from app.services.metrics import metrics_store

                            metrics_store.incr_outbox_dead()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    from app.services.metrics import metrics_store

                    metrics_store.incr_outbox_failed()
                except Exception:
                    pass
                log_event("outbox.publish_failed", org_id=row.org_id, event_id=row.event_id, error=str(exc))
        return PublishSummary(
            claimed=len(rows), published=published, failed=failed, deduped=deduped, dead=dead
        )


outbox_publisher = OutboxPublisher()
