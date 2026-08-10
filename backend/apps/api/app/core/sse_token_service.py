"""Short-lived SSE stream tokens — replaces query-string JWT (SEC-03)."""

from __future__ import annotations

import hashlib
import secrets
import time

from app.core.config import settings
from app.services.redis_client import get_redis_client

_PREFIX = "iam:sse_token"
_DEFAULT_TTL = 300


def _key(token_hash: str) -> str:
    return f"{_PREFIX}:{token_hash}"


def issue_sse_token(*, org_id: str, user_id: str, session_id: str | None = None) -> tuple[str, int]:
    """Return (raw_token, ttl_seconds). Raw token is single-use for stream connection."""
    client = get_redis_client()
    if client is None:
        raise RuntimeError("Redis required for SSE stream tokens")
    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    ttl = int(getattr(settings, "sse_token_ttl_seconds", _DEFAULT_TTL))
    payload = f"{org_id}|{user_id}|{session_id or ''}|{int(time.time())}"
    client.setex(_key(token_hash), ttl, payload)
    return raw, ttl


def consume_sse_token(raw_token: str) -> dict[str, str] | None:
    """Validate and consume token (one-time). Returns org_id, user_id, session_id."""
    client = get_redis_client()
    if client is None or not raw_token.strip():
        return None
    token_hash = hashlib.sha256(raw_token.strip().encode()).hexdigest()
    stored = client.get(_key(token_hash))
    if not stored:
        return None
    client.delete(_key(token_hash))
    parts = str(stored).split("|", 3)
    if len(parts) < 2:
        return None
    return {
        "org_id": parts[0],
        "user_id": parts[1],
        "session_id": parts[2] if len(parts) > 2 and parts[2] else None,
    }
