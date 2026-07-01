"""Short-lived cache so duplicate concurrent refresh requests succeed after rotation."""
from __future__ import annotations

import hashlib
import time
from typing import Any

_GRACE_SECONDS = 30
_cache: dict[str, tuple[dict[str, Any], float]] = {}


def _key(raw_refresh_token: str) -> str:
    return hashlib.sha256(raw_refresh_token.encode("utf-8")).hexdigest()


def store_grace_result(raw_refresh_token: str, result: dict[str, Any]) -> None:
    _cache[_key(raw_refresh_token)] = (result, time.time() + _GRACE_SECONDS)


def get_grace_result(raw_refresh_token: str) -> dict[str, Any] | None:
    entry = _cache.get(_key(raw_refresh_token))
    if not entry:
        return None
    result, expires_at = entry
    if expires_at < time.time():
        _cache.pop(_key(raw_refresh_token), None)
        return None
    return result
