from __future__ import annotations

import json
from typing import Any

from app.core.config import settings


_CACHE: dict[str, tuple[float, Any]] = {}
_TTL_SECONDS = 60.0


def _cache_key(org_id: str, kind: str) -> str:
    return f"policy:{kind}:{org_id}"


def _redis_client():
    if not (settings.redis_url or "").strip():
        return None
    try:
        import redis

        return redis.Redis.from_url(settings.redis_url, decode_responses=True)
    except Exception:
        return None


def get_cached(org_id: str, kind: str) -> Any | None:
    key = _cache_key(org_id, kind)
    client = _redis_client()
    if client:
        try:
            raw = client.get(key)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    import time

    entry = _CACHE.get(key)
    if entry and (time.time() - entry[0]) < _TTL_SECONDS:
        return entry[1]
    return None


def set_cached(org_id: str, kind: str, value: Any) -> None:
    key = _cache_key(org_id, kind)
    import time

    _CACHE[key] = (time.time(), value)
    client = _redis_client()
    if client:
        try:
            client.setex(key, int(_TTL_SECONDS), json.dumps(value, default=str))
        except Exception:
            pass


def invalidate_org(org_id: str) -> None:
    for kind in ("rules", "matrix"):
        key = _cache_key(org_id, kind)
        _CACHE.pop(key, None)
        client = _redis_client()
        if client:
            try:
                client.delete(key)
            except Exception:
                pass
