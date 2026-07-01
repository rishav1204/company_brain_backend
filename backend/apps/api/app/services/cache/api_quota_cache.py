from __future__ import annotations

import logging
import threading
from datetime import date
from typing import Any

from app.modules.platform.billing.exceptions import QuotaExceeded
from app.modules.platform.billing.repositories.billing_repository import billing_repository
from app.modules.platform.billing.services.usage_service import usage_service
from app.services.redis_client import get_redis_client

logger = logging.getLogger(__name__)

_PLAN_LIMIT_TTL = 300
_FLUSH_EVERY = 25
_lock = threading.Lock()
_flush_pending: set[str] = set()


def _period_start() -> str:
    today = date.today()
    return today.replace(day=1).isoformat()


def _counter_key(org_id: str) -> str:
    return f"quota:{org_id}:api_calls:{_period_start()}"


def _flushed_key(org_id: str) -> str:
    return f"quota:flushed:{org_id}:{_period_start()}"


def _plan_limit_key(org_id: str) -> str:
    return f"quota:plan_limit:{org_id}"


def _get_cached_limit(org_id: str) -> int | None:
    client = get_redis_client()
    if client is not None:
        try:
            raw = client.get(_plan_limit_key(org_id))
            if raw is not None:
                if raw == b"unlimited" or raw == "unlimited":
                    return None
                return int(raw)
        except Exception:
            logger.debug("quota plan limit cache read failed org=%s", org_id, exc_info=True)
    limit = usage_service.get_limit(org_id, "api_calls_monthly")
    if client is not None:
        try:
            client.setex(
                _plan_limit_key(org_id),
                _PLAN_LIMIT_TTL,
                "unlimited" if limit is None else str(limit),
            )
        except Exception:
            pass
    return limit


def invalidate_plan_limit(org_id: str) -> None:
    client = get_redis_client()
    if client is not None:
        try:
            client.delete(_plan_limit_key(org_id))
        except Exception:
            pass


def _bootstrap_counter(client: Any, org_id: str) -> int:
    key = _counter_key(org_id)
    if client.exists(key):
        return int(client.get(key) or 0)
    baseline = billing_repository.get_usage_metric(org_id, "api_calls")
    flushed = billing_repository.get_usage_metric(org_id, "api_calls")
    client.set(key, baseline, ex=35 * 24 * 3600)
    client.set(_flushed_key(org_id), flushed, ex=35 * 24 * 3600)
    return baseline


def check_and_increment(org_id: str) -> None:
    """Fast Redis quota check; falls back to DB when Redis unavailable."""
    client = get_redis_client()
    if client is None:
        logger.warning("api_quota_cache: Redis unavailable, using DB fallback org=%s", org_id)
        usage_service.check_quota(org_id, "api_calls_monthly", increment=1)
        return

    limit = _get_cached_limit(org_id)
    try:
        with _lock:
            current = _bootstrap_counter(client, org_id)
            new_val = int(client.incr(_counter_key(org_id)))
        if limit is not None and new_val > limit:
            client.decr(_counter_key(org_id))
            raise QuotaExceeded("api_calls_monthly", new_val - 1, limit)
        if new_val % _FLUSH_EVERY == 0:
            _schedule_flush(org_id)
    except QuotaExceeded:
        raise
    except Exception:
        logger.warning("api_quota_cache: Redis error, DB fallback org=%s", org_id, exc_info=True)
        usage_service.check_quota(org_id, "api_calls_monthly", increment=1)


def _schedule_flush(org_id: str) -> None:
    with _lock:
        if org_id in _flush_pending:
            return
        _flush_pending.add(org_id)

    def _run() -> None:
        try:
            flush_to_db(org_id)
        finally:
            with _lock:
                _flush_pending.discard(org_id)

    threading.Thread(target=_run, daemon=True).start()


def flush_to_db(org_id: str) -> None:
    client = get_redis_client()
    if client is None:
        return
    try:
        counter_key = _counter_key(org_id)
        flushed_key = _flushed_key(org_id)
        current = int(client.get(counter_key) or 0)
        last_flushed = int(client.get(flushed_key) or 0)
        delta = current - last_flushed
        if delta <= 0:
            return
        billing_repository.record_usage_event(org_id, metric_code="api_calls", delta=delta)
        client.set(flushed_key, current, ex=35 * 24 * 3600)
    except Exception:
        logger.warning("api_quota_cache: flush failed org=%s", org_id, exc_info=True)
