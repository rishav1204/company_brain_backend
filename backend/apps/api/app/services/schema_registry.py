from __future__ import annotations

import logging
import threading
import time

from app.services.db import get_db_conn

logger = logging.getLogger(__name__)

_TTL_SECONDS = 300
_lock = threading.Lock()
_cache: dict[str, tuple[float, bool]] = {}
_core_ready: bool | None = None


def _cache_get(key: str) -> bool | None:
    with _lock:
        entry = _cache.get(key)
        if entry and entry[0] > time.time():
            return entry[1]
    return None


def _cache_set(key: str, ready: bool) -> bool:
    with _lock:
        _cache[key] = (time.time() + _TTL_SECONDS, ready)
    return ready


def table_ready(schema: str, table: str) -> bool:
    key = f"{schema}.{table}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = %s
                    LIMIT 1
                    """,
                    (schema, table),
                )
                ready = cur.fetchone() is not None
    except Exception:
        logger.debug("schema_registry probe failed %s", key, exc_info=True)
        ready = False
    return _cache_set(key, ready)


def set_core_ready(ready: bool) -> None:
    global _core_ready
    with _lock:
        _core_ready = ready
        _cache["core.ready"] = (time.time() + _TTL_SECONDS, ready)


def is_core_ready() -> bool:
    global _core_ready
    if _core_ready is not None:
        return _core_ready
    cached = _cache_get("core.ready")
    if cached is not None:
        _core_ready = cached
        return cached
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'core' AND table_name = 'users'
                    LIMIT 1
                    """
                )
                ready = cur.fetchone() is not None
    except Exception:
        ready = False
    set_core_ready(ready)
    return ready


def warm_common_tables() -> None:
    """Probe frequently checked tables once at startup."""
    for schema, table in (
        ("core", "users"),
        ("billing", "subscriptions"),
        ("billing", "usage_metrics"),
        ("finance_analytics", "kpi_snapshots"),
        ("finance_analytics", "dashboard_snapshots"),
        ("governance", "policies"),
    ):
        table_ready(schema, table)
