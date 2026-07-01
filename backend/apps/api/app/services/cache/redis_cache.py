from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from app.services.redis_client import get_redis_client

logger = logging.getLogger(__name__)

_PREFIX = "cache"
_DEFAULT_TTL = 60
_NAMESPACE_TTLS: dict[str, int] = {
    "billing.plan": 300,
    "iam.permissions": 60,
    "analytics.dashboard": 60,
    "analytics.kpis": 60,
    "analytics.trends": 120,
    "analytics.benchmark": 60,
    "analytics.close": 60,
}

# In-process fallback when Redis is unavailable (per-worker).
_mem: dict[str, tuple[float, Any]] = {}


def _redis_key(org_id: str, namespace: str, params_hash: str) -> str:
    return f"{_PREFIX}:{org_id}:{namespace}:{params_hash}"


def _params_hash(params: dict[str, Any] | None) -> str:
    if not params:
        return "default"
    normalized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _ttl_for(namespace: str, ttl: int | None) -> int:
    if ttl is not None:
        return max(1, int(ttl))
    for prefix, default in _NAMESPACE_TTLS.items():
        if namespace == prefix or namespace.startswith(prefix.rstrip("*")):
            return default
    return _DEFAULT_TTL


def get_cached(
    org_id: str,
    namespace: str,
    params: dict[str, Any] | None = None,
) -> Any | None:
    ph = _params_hash(params)
    key = _redis_key(org_id, namespace, ph)
    client = get_redis_client()
    if client is not None:
        try:
            raw = client.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            logger.debug("redis_cache get failed key=%s", key, exc_info=True)
    entry = _mem.get(key)
    if entry and entry[0] > time.time():
        return entry[1]
    return None


def set_cached(
    org_id: str,
    namespace: str,
    value: Any,
    params: dict[str, Any] | None = None,
    *,
    ttl: int | None = None,
) -> None:
    ph = _params_hash(params)
    key = _redis_key(org_id, namespace, ph)
    seconds = _ttl_for(namespace, ttl)
    payload = json.dumps(value, default=str)
    client = get_redis_client()
    if client is not None:
        try:
            client.setex(key, seconds, payload)
        except Exception:
            logger.debug("redis_cache set failed key=%s", key, exc_info=True)
    _mem[key] = (time.time() + seconds, value)


def invalidate_key(
    org_id: str,
    namespace: str,
    params: dict[str, Any] | None = None,
) -> None:
    ph = _params_hash(params)
    key = _redis_key(org_id, namespace, ph)
    client = get_redis_client()
    if client is not None:
        try:
            client.delete(key)
        except Exception:
            logger.debug("redis_cache invalidate_key failed key=%s", key, exc_info=True)
    _mem.pop(key, None)


def invalidate_namespace(org_id: str, namespace: str) -> int:
    """Delete all keys for org_id + namespace prefix (or analytics.* wildcard)."""
    pattern_ns = namespace.rstrip(".*")
    prefix = f"{_PREFIX}:{org_id}:{pattern_ns}"
    deleted = 0
    client = get_redis_client()
    if client is not None:
        try:
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor=cursor, match=f"{prefix}*", count=100)
                if keys:
                    deleted += int(client.delete(*keys))
                if cursor == 0:
                    break
        except Exception:
            logger.debug("redis_cache invalidate_namespace scan failed org=%s ns=%s", org_id, namespace, exc_info=True)
    stale = [k for k in _mem if k.startswith(prefix)]
    for k in stale:
        _mem.pop(k, None)
        deleted += 1
    return deleted


def cache_hit_metric(namespace: str) -> None:
    try:
        from app.services.metrics.prometheus_exporter import record_cache_hit

        record_cache_hit(namespace, hit=True)
    except Exception:
        pass


def cache_miss_metric(namespace: str) -> None:
    try:
        from app.services.metrics.prometheus_exporter import record_cache_hit

        record_cache_hit(namespace, hit=False)
    except Exception:
        pass
