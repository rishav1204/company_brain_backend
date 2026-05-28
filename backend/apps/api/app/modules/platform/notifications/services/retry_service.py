from __future__ import annotations

from app.core.config import settings


def notification_retry_delay(attempt: int) -> int:
    base = settings.notification_retry_base_seconds
    capped = min(max(attempt, 0), settings.notification_retry_max_attempts)
    return int(base * (2**capped))


def should_retry_notification(attempt: int) -> bool:
    return attempt < settings.notification_retry_max_attempts
