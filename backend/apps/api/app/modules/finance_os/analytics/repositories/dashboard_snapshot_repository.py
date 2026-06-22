from __future__ import annotations

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class DashboardSnapshotRepository:
    def upsert(self, org_id: str, *, snapshot_date: str, payload: dict) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_analytics.dashboard_snapshots (org_id, snapshot_date, payload, refreshed_at)
                    VALUES (%s::uuid, %s::date, %s::jsonb, now())
                    ON CONFLICT (org_id, snapshot_date)
                    DO UPDATE SET payload = EXCLUDED.payload, refreshed_at = now()
                    RETURNING snapshot_date::text, refreshed_at::text
                    """,
                    (org_id, snapshot_date, Json(payload)),
                )
                return dict(cur.fetchone() or {})

    def get_latest(self, org_id: str, *, snapshot_date: str | None = None) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if snapshot_date:
                    cur.execute(
                        """
                        SELECT snapshot_date::text, payload, refreshed_at::text
                        FROM finance_analytics.dashboard_snapshots
                        WHERE org_id = %s::uuid AND snapshot_date = %s::date
                        """,
                        (org_id, snapshot_date),
                    )
                else:
                    cur.execute(
                        """
                        SELECT snapshot_date::text, payload, refreshed_at::text
                        FROM finance_analytics.dashboard_snapshots
                        WHERE org_id = %s::uuid
                        ORDER BY snapshot_date DESC LIMIT 1
                        """,
                        (org_id,),
                    )
                row = cur.fetchone()
                return dict(row) if row else None


dashboard_snapshot_repository = DashboardSnapshotRepository()
