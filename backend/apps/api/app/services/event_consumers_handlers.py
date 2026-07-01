"""Compatibility shim — handlers live in platform.events.consumers.handlers."""
from __future__ import annotations

import app.modules.platform.events.consumers.handlers.legacy_handlers as _legacy

__all__ = [name for name in dir(_legacy) if name.startswith("_consume") and not name.startswith("__")]


def __getattr__(name: str):
    return getattr(_legacy, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_legacy)))
