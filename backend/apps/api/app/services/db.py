from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings


def _dsn() -> str:
    return getattr(settings, "postgres_dsn", "") or ""


@contextmanager
def get_db_conn():
    dsn = _dsn()
    if not dsn:
        raise RuntimeError("POSTGRES_DSN is required for production data layer")
    if settings.postgres_require_tls and "sslmode=" not in dsn.lower():
        separator = "&" if "?" in dsn else "?"
        dsn = f"{dsn}{separator}sslmode=require"
    conn = psycopg.connect(dsn, row_factory=dict_row, autocommit=False, connect_timeout=15)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_rls_org(conn, org_id: str) -> None:
    normalized = str(org_id or "").strip()
    if not normalized:
        raise ValueError("org_id is required for tenant-scoped database access")
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_org', %s, true)", (normalized,))
