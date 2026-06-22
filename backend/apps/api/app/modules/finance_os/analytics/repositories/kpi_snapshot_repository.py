from __future__ import annotations

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class KpiSnapshotRepository:
    def upsert(
        self,
        org_id: str,
        *,
        kpi_code: str,
        kpi_value: float,
        snapshot_date: str,
        metadata: dict | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_analytics.kpi_snapshots (
                      org_id, kpi_code, kpi_value, snapshot_date, metadata
                    )
                    VALUES (%s::uuid, %s, %s::numeric, %s::date, %s::jsonb)
                    ON CONFLICT (org_id, kpi_code, snapshot_date)
                    DO UPDATE SET kpi_value = EXCLUDED.kpi_value, metadata = EXCLUDED.metadata, created_at = now()
                    RETURNING kpi_code, kpi_value, snapshot_date::text
                    """,
                    (org_id, kpi_code, float(kpi_value), snapshot_date, Json(metadata or {})),
                )
                return dict(cur.fetchone() or {})

    def list(
        self,
        org_id: str,
        *,
        kpi_codes: list[str] | None = None,
        snapshot_date: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        limit = max(1, min(int(limit or 100), 500))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if snapshot_date and kpi_codes:
                    cur.execute(
                        """
                        SELECT kpi_code, kpi_value, snapshot_date::text, metadata, created_at::text
                        FROM finance_analytics.kpi_snapshots
                        WHERE org_id = %s::uuid AND snapshot_date = %s::date
                          AND kpi_code = ANY(%s)
                        ORDER BY kpi_code ASC
                        LIMIT %s
                        """,
                        (org_id, snapshot_date, kpi_codes, limit),
                    )
                elif snapshot_date:
                    cur.execute(
                        """
                        SELECT kpi_code, kpi_value, snapshot_date::text, metadata, created_at::text
                        FROM finance_analytics.kpi_snapshots
                        WHERE org_id = %s::uuid AND snapshot_date = %s::date
                        ORDER BY kpi_code ASC
                        LIMIT %s
                        """,
                        (org_id, snapshot_date, limit),
                    )
                elif kpi_codes:
                    cur.execute(
                        """
                        SELECT kpi_code, kpi_value, snapshot_date::text, metadata, created_at::text
                        FROM finance_analytics.kpi_snapshots
                        WHERE org_id = %s::uuid AND kpi_code = ANY(%s)
                        ORDER BY snapshot_date DESC, kpi_code ASC
                        LIMIT %s
                        """,
                        (org_id, kpi_codes, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT kpi_code, kpi_value, snapshot_date::text, metadata, created_at::text
                        FROM finance_analytics.kpi_snapshots
                        WHERE org_id = %s::uuid
                        ORDER BY snapshot_date DESC, kpi_code ASC
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in (cur.fetchall() or [])]

    def history(self, org_id: str, *, kpi_code: str, limit: int = 12) -> list[dict]:
        limit = max(1, min(int(limit or 12), 60))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT kpi_code, kpi_value, snapshot_date::text, metadata
                    FROM finance_analytics.kpi_snapshots
                    WHERE org_id = %s::uuid AND kpi_code = %s
                    ORDER BY snapshot_date DESC
                    LIMIT %s
                    """,
                    (org_id, kpi_code, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


kpi_snapshot_repository = KpiSnapshotRepository()
