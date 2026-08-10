"""Verify FORCE ROW LEVEL SECURITY on core.* and erp.* tables (DB-01)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "backend" / "apps" / "api"
ENV_PATH = API_ROOT / ".env"

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


def _load_env_file() -> None:
    if not ENV_PATH.is_file():
        return
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    _load_env_file()
    from app.services.db import get_db_conn

    failures: list[str] = []
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT n.nspname AS schema_name, c.relname AS table_name,
                       c.relrowsecurity AS rls_enabled, c.relforcerowsecurity AS force_rls
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname IN ('core', 'erp')
                  AND c.relkind = 'r'
                ORDER BY 1, 2
                """
            )
            rows = cur.fetchall() or []
            for row in rows:
                schema = str(row["schema_name"])
                table = str(row["table_name"])
                if not row.get("rls_enabled"):
                    failures.append(f"rls_disabled:{schema}.{table}")
                elif not row.get("force_rls"):
                    failures.append(f"force_rls_missing:{schema}.{table}")
    if failures:
        print("FORCE_RLS_VERIFICATION_FAILED", failures)
        return 1
    print("FORCE_RLS_VERIFICATION_OK", len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
