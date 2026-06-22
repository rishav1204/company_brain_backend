#!/usr/bin/env python3
"""Bootstrap erp_reporting materialized snapshots for an org/period."""

from __future__ import annotations

import argparse
import os
import sys

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API_ROOT = os.path.join(BACKEND, "apps", "api")
sys.path.insert(0, API_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap M31 erp_reporting snapshots")
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--fiscal-period-id", default=None)
    parser.add_argument("--as-of-date", default=None)
    args = parser.parse_args()

    from app.modules.erp.reporting.engine import materialization_engine
    from app.modules.erp.reporting.repositories.schema_repository import reporting_schema_repository

    if not reporting_schema_repository.schema_ready():
        print("erp_reporting schema not ready — run migration 056 first")
        return 1

    org_id = args.org_id
    if args.fiscal_period_id:
        result = materialization_engine.refresh_all_for_period(
            org_id, fiscal_period_id=args.fiscal_period_id, as_of_date=args.as_of_date
        )
    else:
        from datetime import date

        as_of = args.as_of_date or date.today().isoformat()
        result = {
            "ap_aging": materialization_engine.refresh_ap_aging(org_id, as_of_date=as_of),
            "ar_aging": materialization_engine.refresh_ar_aging(org_id, as_of_date=as_of),
        }
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
