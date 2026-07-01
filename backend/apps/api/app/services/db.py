from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING

from psycopg.rows import dict_row

from app.core.config import settings

if TYPE_CHECKING:
    from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def _dsn() -> str:
    return getattr(settings, "postgres_dsn", "") or ""


def _connection_dsn() -> str:
    dsn = _dsn()
    if not dsn:
        raise RuntimeError("POSTGRES_DSN is required for production data layer")
    if settings.postgres_require_tls and "sslmode=" not in dsn.lower():
        separator = "&" if "?" in dsn else "?"
        dsn = f"{dsn}{separator}sslmode=require"
    return dsn


def _check_pool_connection(conn) -> None:
    """Discard stale connections (common with Neon pooler idle timeouts)."""
    conn.rollback()
    with conn.cursor() as cur:
        cur.execute("SELECT 1")
    conn.rollback()


def _reset_pool_connection(conn) -> None:
    conn.rollback()


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        from psycopg_pool import ConnectionPool

        _pool = ConnectionPool(
            conninfo=_connection_dsn(),
            min_size=settings.postgres_pool_min,
            max_size=settings.postgres_pool_max,
            kwargs={"row_factory": dict_row, "connect_timeout": 15},
            check=_check_pool_connection,
            reset=_reset_pool_connection,
            max_lifetime=600,
            max_idle=120,
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def get_db_conn():
    pool = _get_pool()
    with pool.connection() as conn:
        conn.autocommit = False
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def set_rls_org(conn, org_id: str) -> None:
    normalized = str(org_id or "").strip()
    if not normalized:
        raise ValueError("org_id is required for tenant-scoped database access")
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_org', %s, true)", (normalized,))
