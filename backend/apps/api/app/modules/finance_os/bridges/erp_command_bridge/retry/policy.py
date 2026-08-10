"""Retry policy for retriable command failures (infrastructure / ERP)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from app.modules.finance_os.bridges.erp_command_bridge.exceptions import BridgeError, classify_exception

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    base_delay_seconds: float = 0.05
    max_delay_seconds: float = 1.0
    # When True, only retry infrastructure/timeout by default
    infrastructure_only: bool = True


DEFAULT_POLICY = RetryPolicy(max_attempts=1)


def run_with_retry(fn: Callable[[], T], *, policy: RetryPolicy | None = None) -> T:
    policy = policy or DEFAULT_POLICY
    last_exc: BaseException | None = None
    for attempt in range(1, max(policy.max_attempts, 1) + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            err_class, _code, retryable = classify_exception(exc)
            if attempt >= policy.max_attempts or not retryable:
                raise
            if policy.infrastructure_only and err_class.value not in {"infrastructure", "timeout", "erp_failure"}:
                raise
            delay = min(policy.base_delay_seconds * (2 ** (attempt - 1)), policy.max_delay_seconds)
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc
