"""Verify NOT VALID constraints are validated in production (DB-13)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "backend" / "apps" / "api"
ENV_PATH = API_ROOT / ".env"

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

_CONSTRAINTS = (
    "chk_erp_journals_company_id_not_null",
    "chk_erp_ap_invoices_company_id_not_null",
    "chk_erp_ar_invoices_company_id_not_null",
    "chk_erp_vouchers_company_id_not_null",
)


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
            for name in _CONSTRAINTS:
                cur.execute(
                    """
                    SELECT convalidated
                    FROM pg_constraint
                    WHERE conname = %s
                    """,
                    (name,),
                )
                row = cur.fetchone()
                if not row:
                    failures.append(f"missing:{name}")
                elif not row.get("convalidated"):
                    failures.append(f"not_validated:{name}")
    if failures:
        print("CONSTRAINT_VERIFICATION_FAILED", failures)
        return 1
    print("CONSTRAINT_VERIFICATION_OK", len(_CONSTRAINTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
