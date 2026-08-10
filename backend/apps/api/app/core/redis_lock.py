"""Distributed Redis locks for correctness-critical sections (RQ-11)."""

from __future__ import annotations

import random
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Iterator

from app.services.redis_client import get_redis_client

_UNLOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

_RENEW_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("expire", KEYS[1], tonumber(ARGV[2]))
else
    return 0
end
"""


def _sleep_backoff(attempt: int, *, base: float = 0.02, cap: float = 0.25) -> None:
    # Small jitter reduces lock convoy under contention.
    delay = min(cap, base * (2**min(attempt, 6)))
    time.sleep(delay * (0.5 + random.random()))


@contextmanager
def redis_lock(
    key: str,
    *,
    ttl_seconds: int = 30,
    wait_seconds: float = 5.0,
    renew: bool = True,
    renew_interval_seconds: float | None = None,
) -> Iterator[None]:
    """
    Production-grade Redis lease lock:
    - SET NX EX lease (automatic expiration)
    - Token-based safe unlock (ownership validation)
    - Optional lease renewal thread for long critical sections
    - Bounded wait with jittered backoff

    Notes:
    - Use ONLY where serialization is required for correctness (payments, posting, close, leader election).
    - In prod, Redis must be configured; we fail closed.
    """
    client = get_redis_client()
    if client is None:
        from app.core.config import settings

        if settings.app_env.lower() == "prod":
            raise RuntimeError("Redis required for distributed lock in production")
        yield
        return

    lock_key = f"lock:{key}"
    token = uuid.uuid4().hex
    deadline = time.monotonic() + max(0.0, float(wait_seconds))
    attempt = 0
    while True:
        if client.set(lock_key, token, nx=True, ex=int(ttl_seconds)):
            break
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Could not acquire lock: {key}")
        _sleep_backoff(attempt)
        attempt += 1

    stop = threading.Event()
    renew_thread: threading.Thread | None = None
    if renew:
        interval = renew_interval_seconds
        if interval is None:
            interval = max(1.0, float(ttl_seconds) / 3.0)

        def _renewer() -> None:
            while not stop.wait(interval):
                try:
                    client.eval(_RENEW_LUA, 1, lock_key, token, int(ttl_seconds))
                except Exception:
                    # If renewal fails transiently, lease still protects via TTL.
                    pass

        renew_thread = threading.Thread(target=_renewer, name="redis_lock_renewer", daemon=True)
        renew_thread.start()

    try:
        yield
    finally:
        stop.set()
        try:
            client.eval(_UNLOCK_LUA, 1, lock_key, token)
        except Exception:
            pass
