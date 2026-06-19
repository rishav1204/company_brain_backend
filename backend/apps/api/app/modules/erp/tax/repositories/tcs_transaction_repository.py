from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class TcsTransactionRepository:
    def create(self, org_id: str, **fields) -> dict:
        tid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.tcs_transactions (
                      id, org_id, source_type, source_id, customer_id, section_code,
                      gross_amount, tcs_amount, total_collected, status, return_period,
                      financial_year, quarter, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s,%s::uuid,%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                    ON CONFLICT (org_id, source_type, source_id, section_code) DO UPDATE
                      SET tcs_amount=EXCLUDED.tcs_amount, total_collected=EXCLUDED.total_collected
                    RETURNING id::text, section_code, tcs_amount, total_collected
                    """,
                    (
                        tid,
                        org_id,
                        fields["source_type"],
                        fields["source_id"],
                        fields.get("customer_id"),
                        fields.get("section_code", "206C"),
                        fields["gross_amount"],
                        fields["tcs_amount"],
                        fields["total_collected"],
                        fields.get("status", "calculated"),
                        fields.get("return_period"),
                        fields.get("financial_year"),
                        fields.get("quarter"),
                        Json(fields.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": tid})

    def get_by_source(self, org_id: str, *, source_type: str, source_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, source_type, source_id::text, customer_id::text, section_code,
                           gross_amount, tcs_amount, total_collected, status
                    FROM erp.tcs_transactions
                    WHERE org_id=%s::uuid AND source_type=%s AND source_id=%s::uuid
                    LIMIT 1
                    """,
                    (org_id, source_type, source_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def sum_ytd(self, org_id: str, *, customer_id: str, section_code: str, financial_year: str) -> float:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(gross_amount), 0) AS total
                    FROM erp.tcs_transactions
                    WHERE org_id=%s::uuid AND customer_id=%s::uuid AND section_code=%s AND financial_year=%s
                    """,
                    (org_id, customer_id, section_code, financial_year),
                )
                row = cur.fetchone()
                return float(row["total"] if row else 0)

    def list(self, org_id: str, *, limit: int = 200) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, source_type, source_id::text, customer_id::text, section_code,
                           gross_amount, tcs_amount, total_collected, status, return_period
                    FROM erp.tcs_transactions
                    WHERE org_id=%s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


tcs_transaction_repository = TcsTransactionRepository()
