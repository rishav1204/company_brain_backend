from __future__ import annotations

import hashlib
import json
import time
from typing import Any

_CACHE: dict[str, tuple[float, Any]] = {}
_DEFAULT_TTL = 30.0


def _key(org_id: str, report_type: str, params: dict) -> str:
    raw = json.dumps({"org_id": org_id, "report_type": report_type, "params": params}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def get_cached(org_id: str, report_type: str, params: dict) -> Any | None:
    k = _key(org_id, report_type, params)
    entry = _CACHE.get(k)
    if not entry:
        return None
    expires, value = entry
    if time.time() > expires:
        _CACHE.pop(k, None)
        return None
    return value


def set_cached(org_id: str, report_type: str, params: dict, value: Any, *, ttl: float = _DEFAULT_TTL) -> None:
    k = _key(org_id, report_type, params)
    _CACHE[k] = (time.time() + ttl, value)


def is_stale(refreshed_at: str | None, *, max_age_seconds: float = 3600.0) -> bool:
    if not refreshed_at:
        return True
    try:
        from datetime import datetime

        ts = datetime.fromisoformat(refreshed_at.replace("Z", "+00:00"))
        age = time.time() - ts.timestamp()
        return age > max_age_seconds
    except Exception:
        return True
