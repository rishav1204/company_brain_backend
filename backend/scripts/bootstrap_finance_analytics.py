#!/usr/bin/env python3
"""Bootstrap finance_analytics KPI snapshots for an org."""

from __future__ import annotations

import argparse
import os
import sys

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API_ROOT = os.path.join(BACKEND, "apps", "api")
sys.path.insert(0, API_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap M32 finance_analytics KPIs")
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--fiscal-period-id", default=None)
    args = parser.parse_args()

    from app.modules.finance_os.analytics.pipelines.analytics_refresh_pipeline import run_refresh
    from app.modules.finance_os.analytics.repositories.schema_repository import analytics_schema_repository

    if not analytics_schema_repository.schema_ready():
        print("finance_analytics schema not ready — run migration 057 first")
        return 1

    result = run_refresh(args.org_id, fiscal_period_id=args.fiscal_period_id)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
