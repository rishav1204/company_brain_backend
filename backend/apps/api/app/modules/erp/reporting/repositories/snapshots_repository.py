from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class SnapshotsRepository:
    def create(
        self,
        org_id: str,
        *,
        report_type: str,
        period_key: str,
        payload: dict,
        created_by: str | None = None,
    ) -> dict:
        snap_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp_reporting.report_snapshots (
                      id, org_id, report_type, period_key, payload, created_by
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb, %s::uuid)
                    RETURNING id::text, report_type, period_key, created_at::text
                    """,
                    (snap_id, org_id, report_type, period_key, Json(payload), created_by),
                )
                return dict(cur.fetchone() or {"id": snap_id})

    def get_latest(self, org_id: str, *, report_type: str, period_key: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, report_type, period_key, payload, created_at::text
                    FROM erp_reporting.report_snapshots
                    WHERE org_id = %s::uuid AND report_type = %s AND period_key = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (org_id, report_type, period_key),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(
        self,
        org_id: str,
        *,
        report_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        limit = max(1, min(int(limit or 50), 200))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if report_type:
                    cur.execute(
                        """
                        SELECT id::text, report_type, period_key, created_at::text
                        FROM erp_reporting.report_snapshots
                        WHERE org_id = %s::uuid AND report_type = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (org_id, report_type, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, report_type, period_key, created_at::text
                        FROM erp_reporting.report_snapshots
                        WHERE org_id = %s::uuid
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in (cur.fetchall() or [])]


snapshots_repository = SnapshotsRepository()
