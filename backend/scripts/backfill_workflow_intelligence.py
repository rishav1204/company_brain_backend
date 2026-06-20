"""Backfill M26 workflow intelligence snapshots from completed M2 instances."""

from __future__ import annotations

import argparse
import sys

import psycopg

SCRIPT_DIR = __import__("pathlib").Path(__file__).resolve().parent
API_ROOT = SCRIPT_DIR.parent / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    from app.modules.finance_os.workflow_intelligence.pipelines.workflow_intelligence_pipeline import (
        workflow_intelligence_pipeline,
    )

    with psycopg.connect(args.dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text FROM workflow.workflow_instances
                WHERE org_id = %s::uuid AND status IN ('completed', 'failed')
                  AND completed_at >= NOW() - (%s || ' days')::interval
                ORDER BY completed_at DESC LIMIT %s
                """,
                (args.org_id, args.days, args.limit),
            )
            ids = [str(r[0]) for r in cur.fetchall()]

    for iid in ids:
        try:
            workflow_intelligence_pipeline.run(args.org_id, workflow_instance_id=iid)
        except Exception as exc:
            print(f"skip {iid}: {exc}")

    print(f"Processed {len(ids)} instances")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
