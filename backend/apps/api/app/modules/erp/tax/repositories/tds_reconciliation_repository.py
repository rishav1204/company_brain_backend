from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class TdsReconciliationRepository:
    def create(self, org_id: str, **fields) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.tds_reconciliations (
                      id, org_id, source_type, financial_year, quarter, payload, result, status
                    )
                    VALUES (%s::uuid,%s::uuid,%s,%s,%s,%s::jsonb,%s::jsonb,%s)
                    RETURNING id::text, status
                    """,
                    (
                        rid,
                        org_id,
                        fields.get("source_type", "26AS"),
                        fields["financial_year"],
                        fields.get("quarter"),
                        Json(fields.get("payload") or {}),
                        Json(fields.get("result") or {}),
                        fields.get("status", "completed"),
                    ),
                )
                return dict(cur.fetchone() or {"id": rid})

    def list(self, org_id: str, *, limit: int = 50) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, source_type, financial_year, quarter, status, result, created_at::text
                    FROM erp.tds_reconciliations
                    WHERE org_id=%s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


tds_reconciliation_repository = TdsReconciliationRepository()
