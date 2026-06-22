from __future__ import annotations

# Fixed retry schedule per M36 blueprint: 1m, 5m, 15m, 1h, 6h
WEBHOOK_RETRY_DELAYS_SECONDS = (60, 300, 900, 3600, 21600)
WEBHOOK_MAX_ATTEMPTS = len(WEBHOOK_RETRY_DELAYS_SECONDS)


def retry_delay_seconds(attempt: int) -> int:
    idx = max(0, min(int(attempt), len(WEBHOOK_RETRY_DELAYS_SECONDS) - 1))
    return WEBHOOK_RETRY_DELAYS_SECONDS[idx]


def should_retry(attempt: int, max_attempts: int | None = None) -> bool:
    limit = max_attempts if max_attempts is not None else WEBHOOK_MAX_ATTEMPTS
    return int(attempt) < limit


def next_retry_delay(attempt: int) -> int:
    return retry_delay_seconds(attempt)
