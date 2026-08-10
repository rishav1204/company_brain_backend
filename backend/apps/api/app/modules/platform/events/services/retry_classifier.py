from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetryDecision:
    retryable: bool
    category: str
    detail: str


_NON_RETRYABLE_EXCEPTION_TYPES = (
    ValueError,  # validation / business rule
    PermissionError,  # authz / tenancy guard
    KeyError,  # malformed payload
)


def classify_exception(exc: Exception) -> RetryDecision:
    """
    RQ-03: Deterministic retry classification.
    - Never retry validation/malformed/authz.
    - Retry transient infra/network/timeouts.
    """
    msg = str(exc)[:400]
    if isinstance(exc, _NON_RETRYABLE_EXCEPTION_TYPES):
        return RetryDecision(retryable=False, category="non_retryable", detail=msg)

    name = exc.__class__.__name__.lower()
    if "timeout" in name:
        return RetryDecision(retryable=True, category="timeout", detail=msg)
    if "rate" in msg.lower() and "limit" in msg.lower():
        return RetryDecision(retryable=True, category="rate_limit", detail=msg)
    if "redis" in name or "redis" in msg.lower():
        return RetryDecision(retryable=True, category="redis", detail=msg)
    if "psycopg" in name or "database" in msg.lower() or "sql" in msg.lower():
        return RetryDecision(retryable=True, category="database", detail=msg)
    if "http" in name or "url" in name or "network" in msg.lower():
        return RetryDecision(retryable=True, category="network", detail=msg)
    return RetryDecision(retryable=True, category="transient", detail=msg)

