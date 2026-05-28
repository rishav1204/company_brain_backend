"""Seed sample workflows for the benchmark dev org (run once after migrations)."""
import argparse
import sys

import psycopg

DEV_ORG_ID = "11111111-1111-4111-8111-111111111111"


def seed(dsn: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM workflows WHERE org_id = %s::uuid", (DEV_ORG_ID,))
            if cur.fetchone()[0] > 0:
                print("Workflows already seeded for dev org; skipping.")
                return
            cur.execute(
                """
                INSERT INTO workflows (id, org_id, workflow_type, state, owner_user_id, started_at)
                VALUES
                  ('33333333-3333-4333-8333-333333333331'::uuid, %s::uuid, 'ap_invoice', 'pending', NULL, NOW()),
                  ('33333333-3333-4333-8333-333333333332'::uuid, %s::uuid, 'ap_invoice', 'pending_approval', NULL, NOW()),
                  ('44444444-4444-4444-8444-444444444441'::uuid, %s::uuid, 'ar_invoice', 'pending', NULL, NOW()),
                  ('55555555-5555-4555-8555-555555555551'::uuid, %s::uuid, 'close_orchestration', 'blocked', NULL, NOW())
                """,
                (DEV_ORG_ID, DEV_ORG_ID, DEV_ORG_ID, DEV_ORG_ID),
            )
            print("Seeded 4 dev workflows for org", DEV_ORG_ID)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    args = parser.parse_args()
    try:
        seed(args.dsn)
    except Exception as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
