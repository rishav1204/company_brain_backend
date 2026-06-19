from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ArInvoiceRepository:
    def create(
        self,
        org_id: str,
        *,
        customer_id: str,
        invoice_number: str,
        invoice_date: str,
        due_date: str,
        subtotal: float,
        gst_amount: float,
        total_amount: float,
        company_id: str | None = None,
        created_by: str | None = None,
        metadata: dict | None = None,
        revenue_recognition: dict | None = None,
    ) -> dict:
        iid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.ar_invoices (
                      id, org_id, company_id, customer_id, invoice_number, invoice_date, due_date,
                      subtotal, gst_amount, total_amount, created_by, metadata, revenue_recognition
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s::date,%s::date,
                            %s::numeric,%s::numeric,%s::numeric,%s::uuid,%s::jsonb,%s::jsonb)
                    RETURNING id::text, invoice_number, status, total_amount, due_date::text
                    """,
                    (
                        iid, org_id, company_id, customer_id, invoice_number,
                        invoice_date, due_date, subtotal, gst_amount, total_amount,
                        created_by, Json(metadata or {}), Json(revenue_recognition or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": iid})

    def get(self, org_id: str, *, invoice_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, customer_id::text, invoice_number, invoice_date::text, due_date::text,
                           subtotal, gst_amount, total_amount, paid_amount, status, journal_id::text,
                           metadata, revenue_recognition, created_by::text, issued_by::text,
                           company_id::text, created_at::text, updated_at::text
                    FROM erp.ar_invoices
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, invoice_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def update_metadata(self, org_id: str, *, invoice_id: str, metadata: dict) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.ar_invoices
                    SET metadata = %s::jsonb, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, metadata, status
                    """,
                    (Json(metadata), org_id, invoice_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Invoice not found")
                return dict(row)

    def set_status(
        self,
        org_id: str,
        *,
        invoice_id: str,
        status: str,
        issued_by: str | None = None,
        journal_id: str | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.ar_invoices
                    SET status = %s,
                        issued_by = COALESCE(%s::uuid, issued_by),
                        journal_id = COALESCE(%s::uuid, journal_id),
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, journal_id::text
                    """,
                    (status, issued_by, journal_id, org_id, invoice_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Invoice not found")
                return dict(row)

    def record_receipt(self, org_id: str, *, invoice_id: str, amount: float) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.ar_invoices
                    SET paid_amount = paid_amount + %s::numeric,
                        status = CASE
                          WHEN paid_amount + %s::numeric >= total_amount THEN 'paid'
                          WHEN paid_amount + %s::numeric > 0 THEN 'partially_paid'
                          ELSE status
                        END,
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, paid_amount, total_amount, status
                    """,
                    (amount, amount, amount, org_id, invoice_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Invoice not found")
                return dict(row)

    def list(
        self,
        org_id: str,
        *,
        status: str | None = None,
        customer_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        limit = max(1, min(limit, 500))
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if status:
            where.append("status = %s")
            params.append(status)
        if customer_id:
            where.append("customer_id = %s::uuid")
            params.append(customer_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, customer_id::text, invoice_number, invoice_date::text, due_date::text,
                           total_amount, paid_amount, status, journal_id::text
                    FROM erp.ar_invoices
                    WHERE {' AND '.join(where)}
                    ORDER BY due_date ASC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def list_outstanding(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, customer_id::text, invoice_number, due_date::text,
                           total_amount, paid_amount, metadata,
                           (total_amount - paid_amount) AS outstanding
                    FROM erp.ar_invoices
                    WHERE org_id = %s::uuid
                      AND status IN ('issued','partially_paid','overdue')
                      AND total_amount > paid_amount
                    ORDER BY due_date ASC
                    """,
                    (org_id,),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def list_overdue(self, org_id: str, *, as_of: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, customer_id::text, invoice_number, due_date::text,
                           total_amount, paid_amount,
                           (total_amount - paid_amount) AS outstanding
                    FROM erp.ar_invoices
                    WHERE org_id = %s::uuid
                      AND status IN ('issued','partially_paid','overdue')
                      AND due_date < %s::date
                      AND total_amount > paid_amount
                    """,
                    (org_id, as_of),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


ar_invoice_repository = ArInvoiceRepository()
