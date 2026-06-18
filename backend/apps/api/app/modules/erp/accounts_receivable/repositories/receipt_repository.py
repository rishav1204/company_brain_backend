from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ReceiptRepository:
    def create(
        self,
        org_id: str,
        *,
        customer_id: str,
        receipt_number: str,
        receipt_date: str,
        amount: float,
        payment_mode: str,
        bank_account_id: str | None = None,
        company_id: str | None = None,
        created_by: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.customer_receipts (
                      id, org_id, company_id, customer_id, receipt_number, receipt_date,
                      amount, payment_mode, bank_account_id, created_by, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s::date,%s::numeric,%s,%s::uuid,%s::uuid,%s::jsonb)
                    RETURNING id::text, receipt_number, amount, status, payment_mode
                    """,
                    (
                        rid, org_id, company_id, customer_id, receipt_number,
                        receipt_date, amount, payment_mode, bank_account_id, created_by, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": rid})

    def get(self, org_id: str, *, receipt_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, customer_id::text, receipt_number, receipt_date::text,
                           amount, payment_mode, bank_account_id::text, status, journal_id::text,
                           metadata, created_by::text, created_at::text
                    FROM erp.customer_receipts
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, receipt_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def set_status(self, org_id: str, *, receipt_id: str, status: str, journal_id: str | None = None) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.customer_receipts
                    SET status = %s, journal_id = COALESCE(%s::uuid, journal_id), updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, journal_id::text
                    """,
                    (status, journal_id, org_id, receipt_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Receipt not found")
                return dict(row)

    def add_allocation(self, org_id: str, *, receipt_id: str, invoice_id: str, amount: float) -> dict:
        aid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.customer_receipt_allocations (id, org_id, receipt_id, invoice_id, amount)
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::numeric)
                    RETURNING id::text, invoice_id::text, amount
                    """,
                    (aid, org_id, receipt_id, invoice_id, amount),
                )
                return dict(cur.fetchone() or {"id": aid})

    def list(self, org_id: str, *, customer_id: str | None = None, limit: int = 100) -> list[dict]:
        limit = max(1, min(limit, 500))
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if customer_id:
            where.append("customer_id = %s::uuid")
            params.append(customer_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, customer_id::text, receipt_number, receipt_date::text,
                           amount, payment_mode, status, journal_id::text
                    FROM erp.customer_receipts
                    WHERE {' AND '.join(where)}
                    ORDER BY receipt_date DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


receipt_repository = ReceiptRepository()
