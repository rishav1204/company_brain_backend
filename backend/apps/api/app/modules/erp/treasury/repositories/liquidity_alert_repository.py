from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class LiquidityAlertRepository:
    def create(self, org_id: str, *, alert_type: str, severity: str, message: str, metadata: dict | None = None) -> dict:
        aid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.liquidity_alerts (id, org_id, alert_type, severity, message, status, metadata)
                    VALUES (%s::uuid,%s::uuid,%s,%s,%s,'open',%s::jsonb)
                    RETURNING id::text, alert_type, severity, status
                    """,
                    (aid, org_id, alert_type, severity, message, Json(metadata or {})),
                )
                return dict(cur.fetchone() or {"id": aid})

    def list(self, org_id: str, *, status: str | None = "open", limit: int = 100) -> list[dict]:
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if status:
            where.append("status = %s")
            params.append(status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, alert_type, severity, message, status, created_at::text
                    FROM erp.liquidity_alerts
                    WHERE {' AND '.join(where)}
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def acknowledge(self, org_id: str, *, alert_id: str, acknowledged_by: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.liquidity_alerts
                    SET status = 'acknowledged', acknowledged_by = %s::uuid, acknowledged_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status
                    """,
                    (acknowledged_by, org_id, alert_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Alert not found")
                return dict(row)


liquidity_alert_repository = LiquidityAlertRepository()
