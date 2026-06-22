#!/usr/bin/env python3
"""Bootstrap finance_audit timelines from existing audit_logs."""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from app.modules.finance_os.audit_explorer.pipelines.audit_materialization_pipeline import run_backfill


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap M33 finance_audit timelines")
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args()
    result = run_backfill(args.org_id, limit=args.limit)
    print(result)


if __name__ == "__main__":
    main()
