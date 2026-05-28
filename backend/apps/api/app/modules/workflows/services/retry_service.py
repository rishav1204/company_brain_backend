from __future__ import annotations

BASE_DELAY_SECONDS = 30
MAX_RETRIES = 5


def retry_delay_seconds(retry_count: int, policy: dict | None = None) -> int:
    policy = policy or {}
    base = int(policy.get("base_delay_seconds") or BASE_DELAY_SECONDS)
    max_retries = int(policy.get("max_retries") or MAX_RETRIES)
    capped = min(max(retry_count, 0), max_retries)
    multiplier = policy.get("multiplier", 2)
    try:
        mult = float(multiplier)
    except (TypeError, ValueError):
        mult = 2.0
    return int(base * (mult**capped))


def should_retry(retry_count: int, policy: dict | None = None) -> bool:
    policy = policy or {}
    max_retries = int(policy.get("max_retries") or MAX_RETRIES)
    return retry_count < max_retries
