from __future__ import annotations

from app.services.db import get_db_conn, set_rls_org


def list_org_accuracy(org_id: str, *, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit or 100), 500))
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, forecast_id::text, actual_value, forecast_value,
                       variance_percent, calculated_at::text
                FROM finance_os.forecast_accuracy
                WHERE org_id = %s::uuid
                ORDER BY calculated_at DESC
                LIMIT %s
                """,
                (org_id, limit),
            )
            return [dict(r) for r in (cur.fetchall() or [])]
