from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class InvoiceRepository:
    def create(
        self,
        org_id: str,
        *,
        vendor_id: str,
        invoice_number: str,
        invoice_date: str,
        due_date: str,
        invoice_amount: float,
        gst_amount: float,
        total_amount: float,
        source_document_id: str | None = None,
        duplicate_checksum: str | None = None,
        company_id: str | None = None,
        created_by: str | None = None,
        ai_confidence: dict | None = None,
        metadata: dict | None = None,
        purchase_order_id: str | None = None,
        goods_receipt_id: str | None = None,
    ) -> dict:
        iid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.ap_invoices (
                      id, org_id, company_id, vendor_id, invoice_number, invoice_date, due_date,
                      invoice_amount, gst_amount, total_amount, source_document_id,
                      duplicate_checksum, created_by, ai_confidence, metadata,
                      purchase_order_id, goods_receipt_id
                    )
                    VALUES (
                      %s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s::date,%s::date,
                      %s::numeric,%s::numeric,%s::numeric,%s::uuid,
                      %s,%s::uuid,%s::jsonb,%s::jsonb,%s::uuid,%s::uuid
                    )
                    RETURNING id::text, invoice_number, invoice_date::text, due_date::text,
                              invoice_amount, gst_amount, total_amount, status,
                              vendor_id::text, source_document_id::text, created_at::text
                    """,
                    (
                        iid, org_id, company_id, vendor_id, invoice_number,
                        invoice_date, due_date, invoice_amount, gst_amount, total_amount,
                        source_document_id, duplicate_checksum, created_by,
                        Json(ai_confidence or {}), Json(metadata or {}),
                        purchase_order_id, goods_receipt_id,
                    ),
                )
                return dict(cur.fetchone() or {"id": iid})

    def get(self, org_id: str, *, invoice_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, vendor_id::text, invoice_number, invoice_date::text, due_date::text,
                           invoice_amount, gst_amount, total_amount, paid_amount, status,
                           source_document_id::text, journal_id::text, duplicate_checksum,
                           ai_confidence, metadata, created_by::text, approved_by::text,
                           company_id::text, purchase_order_id::text, goods_receipt_id::text,
                           created_at::text, updated_at::text
                    FROM erp.ap_invoices
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, invoice_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def find_duplicate(self, org_id: str, *, duplicate_checksum: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, invoice_number, status, vendor_id::text
                    FROM erp.ap_invoices
                    WHERE org_id = %s::uuid AND duplicate_checksum = %s
                      AND status NOT IN ('cancelled')
                    LIMIT 1
                    """,
                    (org_id, duplicate_checksum),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def update(
        self,
        org_id: str,
        *,
        invoice_id: str,
        invoice_number: str | None = None,
        invoice_date: str | None = None,
        due_date: str | None = None,
        invoice_amount: float | None = None,
        gst_amount: float | None = None,
        total_amount: float | None = None,
        metadata: dict | None = None,
    ) -> dict:
        fields: list[str] = []
        params: list = []
        if invoice_number is not None:
            fields.append("invoice_number = %s")
            params.append(invoice_number)
        if invoice_date is not None:
            fields.append("invoice_date = %s::date")
            params.append(invoice_date)
        if due_date is not None:
            fields.append("due_date = %s::date")
            params.append(due_date)
        if invoice_amount is not None:
            fields.append("invoice_amount = %s::numeric")
            params.append(invoice_amount)
        if gst_amount is not None:
            fields.append("gst_amount = %s::numeric")
            params.append(gst_amount)
        if total_amount is not None:
            fields.append("total_amount = %s::numeric")
            params.append(total_amount)
        if metadata is not None:
            fields.append("metadata = %s::jsonb")
            params.append(Json(metadata))
        if purchase_order_id is not None:
            fields.append("purchase_order_id = %s::uuid")
            params.append(purchase_order_id)
        if goods_receipt_id is not None:
            fields.append("goods_receipt_id = %s::uuid")
            params.append(goods_receipt_id)
        if not fields:
            row = self.get(org_id, invoice_id=invoice_id)
            if not row:
                raise ValueError("Invoice not found")
            return row
        fields.append("updated_at = NOW()")
        params.extend([org_id, invoice_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE erp.ap_invoices
                    SET {', '.join(fields)}
                    WHERE org_id = %s::uuid AND id = %s::uuid
                      AND status IN ('draft', 'pending_review')
                    RETURNING id::text, invoice_number, status, total_amount, metadata
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Invoice not found or not editable")
                return dict(row)

    def set_status(
        self,
        org_id: str,
        *,
        invoice_id: str,
        status: str,
        approved_by: str | None = None,
        journal_id: str | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.ap_invoices
                    SET status = %s,
                        approved_by = COALESCE(%s::uuid, approved_by),
                        journal_id = COALESCE(%s::uuid, journal_id),
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, journal_id::text, approved_by::text
                    """,
                    (status, approved_by, journal_id, org_id, invoice_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Invoice not found")
                return dict(row)

    def patch_metadata(self, org_id: str, *, invoice_id: str, metadata: dict) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.ap_invoices
                    SET metadata = %s::jsonb, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, metadata
                    """,
                    (Json(metadata), org_id, invoice_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Invoice not found")
                return dict(row)

    def record_payment(self, org_id: str, *, invoice_id: str, amount: float) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.ap_invoices
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
        vendor_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        limit = max(1, min(limit, 500))
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if status:
            where.append("status = %s")
            params.append(status)
        if vendor_id:
            where.append("vendor_id = %s::uuid")
            params.append(vendor_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, vendor_id::text, invoice_number, invoice_date::text, due_date::text,
                           total_amount, paid_amount, status, journal_id::text, created_at::text
                    FROM erp.ap_invoices
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
                    SELECT id::text, vendor_id::text, invoice_number, due_date::text,
                           total_amount, paid_amount,
                           (total_amount - paid_amount) AS outstanding
                    FROM erp.ap_invoices
                    WHERE org_id = %s::uuid
                      AND status IN ('approved','partially_paid')
                      AND total_amount > paid_amount
                    ORDER BY due_date ASC
                    """,
                    (org_id,),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


invoice_repository = InvoiceRepository()
