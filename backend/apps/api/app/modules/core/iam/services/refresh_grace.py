"""Short-lived cache so duplicate concurrent refresh requests succeed after rotation (SEC-05)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.redis_client import get_redis_client

_GRACE_SECONDS = 30
_PREFIX = "iam:refresh_grace"


def _key(raw_refresh_token: str) -> str:
    return f"{_PREFIX}:{hashlib.sha256(raw_refresh_token.encode('utf-8')).hexdigest()}"


def store_grace_result(raw_refresh_token: str, result: dict[str, Any]) -> None:
    client = get_redis_client()
    if client is None:
        return
    client.setex(_key(raw_refresh_token), _GRACE_SECONDS, json.dumps(result))


def get_grace_result(raw_refresh_token: str) -> dict[str, Any] | None:
    client = get_redis_client()
    if client is None:
        return None
    stored = client.get(_key(raw_refresh_token))
    if not stored:
        return None
    try:
        return json.loads(str(stored))
    except json.JSONDecodeError:
        return None
