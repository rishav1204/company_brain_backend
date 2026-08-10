"""Apply migrations 080/081 and run DB-04 company_id remediation."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "backend" / "apps" / "api"
SCRIPT_DIR = Path(__file__).resolve().parent

for path in (str(SCRIPT_DIR), str(API_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def main() -> int:
    from run_migrations_from_env import load_dsn, main as migrate_main

    print("Step 1: Apply pending migrations (080, 081)...")
    rc = migrate_main()
    if rc != 0:
        print("Migration step failed.")
        return rc

    print("Step 2: Python metadata remediation pass...")
    from app.modules.erp.security.services.company_remediation_service import company_remediation_service

    py_result = company_remediation_service.run_python_pass()
    print("Python pass:", py_result)

    print("Step 3: Summary...")
    summary = company_remediation_service.summary()
    print("DQ summary:", summary)

    unresolved = int(summary.get("unresolved") or 0)
    invalid_constraints = [
        c for c in (summary.get("constraints") or [])
        if not c.get("convalidated")
    ]
    if unresolved > 0:
        print(
            f"WARNING: {unresolved} unresolved DQ flags remain — "
            "use POST /erp/admin/company-data-quality/{{flag_id}}/remediate for manual correction."
        )
    if invalid_constraints:
        print("WARNING: constraints not validated:", invalid_constraints)
        return 1
    if unresolved > 0:
        return 1
    print("DB-04 remediation complete: all flags resolved, constraints validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
