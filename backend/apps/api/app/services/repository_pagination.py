"""Shared pagination helpers for repository list methods."""
from __future__ import annotations

DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200


def clamp_limit(limit: int | None, *, default: int = DEFAULT_LIST_LIMIT, maximum: int = MAX_LIST_LIMIT) -> int:
    if limit is None:
        return default
    return max(1, min(int(limit), maximum))


def clamp_offset(offset: int | None) -> int:
    if offset is None:
        return 0
    return max(0, int(offset))
