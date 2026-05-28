from __future__ import annotations

import time
from datetime import datetime, timezone

from app.core.config import settings


def retry_delay_seconds(retry_count: int, base_seconds: int | None = None) -> int:
    base = base_seconds if base_seconds is not None else settings.event_retry_base_seconds
    capped = min(max(retry_count, 0), settings.event_retry_max_attempts)
    return int(base * (2**capped))


def should_retry(attempt: int, max_attempts: int | None = None) -> bool:
    limit = max_attempts if max_attempts is not None else settings.event_retry_max_attempts
    return attempt < limit


def next_retry_at(retry_count: int) -> str:
    delay = retry_delay_seconds(retry_count)
    when = datetime.now(timezone.utc).timestamp() + delay
    return datetime.fromtimestamp(when, tz=timezone.utc).isoformat()


def is_ready_for_retry(envelope: dict) -> bool:
    next_at = envelope.get("_next_retry_at")
    if not next_at:
        return True
    try:
        due = datetime.fromisoformat(str(next_at).replace("Z", "+00:00"))
        return datetime.now(timezone.utc) >= due
    except (TypeError, ValueError):
        return True


def schedule_retry(envelope: dict) -> dict:
    attempts = int(envelope.get("_attempts", 0)) + 1
    envelope["_attempts"] = attempts
    envelope["_next_retry_at"] = next_retry_at(attempts)
    envelope["_retry_delay_seconds"] = retry_delay_seconds(attempts)
    return envelope
