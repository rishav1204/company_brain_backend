from __future__ import annotations

from contextvars import ContextVar

_auto_audit_skip: ContextVar[bool] = ContextVar("governance_auto_audit_skip", default=False)


def skip_auto_audit() -> None:
    _auto_audit_skip.set(True)


def should_skip_auto_audit() -> bool:
    return _auto_audit_skip.get()


def reset_auto_audit_skip() -> None:
    _auto_audit_skip.set(False)
