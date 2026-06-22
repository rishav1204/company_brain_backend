from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class AnomalyFlagRepository:
    def create(
        self,
        org_id: str,
        *,
        anomaly_type: str,
        severity: str,
        payload: dict | None = None,
    ) -> dict:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO finance_analytics.anomaly_flags (id, org_id, anomaly_type, severity, payload)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb)
                    RETURNING id::text, anomaly_type, severity, detected_at::text
                    """,
                    (row_id, org_id, anomaly_type, severity, Json(payload or {})),
                )
                return dict(cur.fetchone() or {"id": row_id})

    def list_recent(self, org_id: str, *, limit: int = 20) -> list[dict]:
        limit = max(1, min(int(limit or 20), 100))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, anomaly_type, severity, payload, detected_at::text
                    FROM finance_analytics.anomaly_flags
                    WHERE org_id = %s::uuid
                    ORDER BY detected_at DESC LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def clear_for_org(self, org_id: str) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM finance_analytics.anomaly_flags WHERE org_id = %s::uuid", (org_id,))
                return int(cur.rowcount or 0)


anomaly_flag_repository = AnomalyFlagRepository()
