from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class TdsSectionRepository:
    def list(self, org_id: str, *, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, section_code, section_name, description, rate, rate_pan, rate_no_pan, threshold_amount
                    FROM erp.tds_sections WHERE org_id=%s::uuid AND is_active=true
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def get_by_code(self, org_id: str, *, section_code: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT section_code, section_name, description, rate, rate_pan, rate_no_pan, threshold_amount
                    FROM erp.tds_sections
                    WHERE org_id=%s::uuid AND section_code=%s AND is_active=true LIMIT 1
                    """,
                    (org_id, section_code),
                )
                row = cur.fetchone()
                return dict(row) if row else None


class TdsTransactionRepository:
    def create(self, org_id: str, **fields) -> dict:
        tid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.tds_transactions (
                      id, org_id, source_type, source_id, section_code, gross_amount, tds_amount, net_amount,
                      status, return_period, vendor_id, invoice_id, payment_id, challan_id,
                      financial_year, quarter, deduction_date, metadata
                    )
                    VALUES (
                      %s::uuid,%s::uuid,%s,%s::uuid,%s,%s,%s,%s,%s,%s,
                      %s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s,%s::date,%s::jsonb
                    )
                    ON CONFLICT (org_id, source_type, source_id, section_code) DO UPDATE
                      SET tds_amount=EXCLUDED.tds_amount, net_amount=EXCLUDED.net_amount
                    RETURNING id::text, section_code, tds_amount, net_amount
                    """,
                    (
                        tid, org_id, fields["source_type"], fields["source_id"], fields["section_code"],
                        fields["gross_amount"], fields["tds_amount"], fields["net_amount"],
                        fields.get("status", "calculated"), fields.get("return_period"),
                        fields.get("vendor_id"), fields.get("invoice_id"), fields.get("payment_id"),
                        fields.get("challan_id"), fields.get("financial_year"), fields.get("quarter"),
                        fields.get("deduction_date"), Json(fields.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": tid})

    def get_by_source(self, org_id: str, *, source_type: str, source_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, source_type, source_id::text, section_code, gross_amount, tds_amount,
                           net_amount, status, vendor_id::text, challan_id::text, financial_year, quarter
                    FROM erp.tds_transactions
                    WHERE org_id=%s::uuid AND source_type=%s AND source_id=%s::uuid
                    LIMIT 1
                    """,
                    (org_id, source_type, source_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def sum_ytd(self, org_id: str, *, vendor_id: str, section_code: str, financial_year: str) -> float:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(gross_amount), 0) AS total
                    FROM erp.tds_transactions
                    WHERE org_id=%s::uuid AND vendor_id=%s::uuid AND section_code=%s AND financial_year=%s
                    """,
                    (org_id, vendor_id, section_code, financial_year),
                )
                row = cur.fetchone()
                return float(row["total"] if row else 0)

    def list(self, org_id: str, *, limit: int = 200, vendor_id: str | None = None, status: str | None = None) -> list[dict]:
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if vendor_id:
            where.append("vendor_id = %s::uuid")
            params.append(vendor_id)
        if status:
            where.append("status = %s")
            params.append(status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, source_type, source_id::text, section_code, gross_amount, tds_amount,
                           net_amount, status, vendor_id::text, invoice_id::text, payment_id::text,
                           challan_id::text, financial_year, quarter, deduction_date::text, return_period, metadata
                    FROM erp.tds_transactions
                    WHERE {' AND '.join(where)}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def link_challan(self, org_id: str, *, transaction_ids: list[str], challan_id: str, status: str = "deposited") -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.tds_transactions
                    SET challan_id=%s::uuid, status=%s
                    WHERE org_id=%s::uuid AND id = ANY(%s::uuid[])
                    """,
                    (challan_id, status, org_id, transaction_ids),
                )
                return cur.rowcount


class EInvoiceRepository:
    def create(self, org_id: str, **fields) -> dict:
        eid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.e_invoices (id, org_id, ar_invoice_id, irn, ack_no, ack_date, qr_code, status, raw_response, metadata)
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s::timestamptz,%s,%s,%s::jsonb,%s::jsonb)
                    ON CONFLICT (org_id, ar_invoice_id) DO UPDATE SET irn=EXCLUDED.irn, status=EXCLUDED.status, raw_response=EXCLUDED.raw_response, updated_at=NOW()
                    RETURNING id::text, ar_invoice_id::text, irn, status
                    """,
                    (
                        eid, org_id, fields["ar_invoice_id"], fields.get("irn"), fields.get("ack_no"),
                        fields.get("ack_date"), fields.get("qr_code"), fields.get("status", "generated"),
                        Json(fields.get("raw_response") or {}), Json(fields.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": eid})

    def get_by_invoice(self, org_id: str, *, ar_invoice_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id::text, ar_invoice_id::text, irn, ack_no, ack_date::text, qr_code, status FROM erp.e_invoices WHERE org_id=%s::uuid AND ar_invoice_id=%s::uuid",
                    (org_id, ar_invoice_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None


class EwayBillRepository:
    def create(self, org_id: str, **fields) -> dict:
        eid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.eway_bills (id, org_id, source_type, source_id, eway_bill_no, valid_upto, status, raw_response, metadata)
                    VALUES (%s::uuid,%s::uuid,%s,%s::uuid,%s,%s::timestamptz,%s,%s::jsonb,%s::jsonb)
                    RETURNING id::text, eway_bill_no, status
                    """,
                    (
                        eid, org_id, fields["source_type"], fields["source_id"], fields.get("eway_bill_no"),
                        fields.get("valid_upto"), fields.get("status", "generated"),
                        Json(fields.get("raw_response") or {}), Json(fields.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": eid})

    def get(self, org_id: str, *, eway_bill_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id::text, source_type, source_id::text, eway_bill_no, valid_upto::text, status FROM erp.eway_bills WHERE org_id=%s::uuid AND id=%s::uuid",
                    (org_id, eway_bill_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None


class ComplianceCalendarRepository:
    def upsert_many(self, org_id: str, items: list[dict]) -> int:
        count = 0
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                for item in items:
                    cur.execute(
                        """
                        INSERT INTO erp.compliance_calendar (id, org_id, obligation_type, due_date, return_period, status, metadata)
                        VALUES (%s::uuid,%s::uuid,%s,%s::date,%s,%s,%s::jsonb)
                        """,
                        (str(uuid4()), org_id, item["obligation_type"], item["due_date"], item.get("return_period"), item.get("status", "pending"), Json({})),
                    )
                    count += 1
        return count

    def list(self, org_id: str, *, status: str | None = None, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
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
                    f"SELECT id::text, obligation_type, due_date::text, return_period, status FROM erp.compliance_calendar WHERE {' AND '.join(where)} ORDER BY due_date LIMIT %s",
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def mark_complete(self, org_id: str, *, obligation_type: str, return_period: str | None = None) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if return_period:
                    cur.execute(
                        "UPDATE erp.compliance_calendar SET status='completed', updated_at=NOW() WHERE org_id=%s::uuid AND obligation_type=%s AND return_period=%s AND status='pending'",
                        (org_id, obligation_type, return_period),
                    )
                else:
                    cur.execute(
                        "UPDATE erp.compliance_calendar SET status='completed', updated_at=NOW() WHERE org_id=%s::uuid AND obligation_type=%s AND status='pending'",
                        (org_id, obligation_type),
                    )
                return cur.rowcount


class TaxNoticeRepository:
    def create(self, org_id: str, **fields) -> dict:
        nid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.tax_notices (id, org_id, notice_type, received_date, document_id, status, ai_summary, metadata)
                    VALUES (%s::uuid,%s::uuid,%s,%s::date,%s::uuid,%s,%s,%s::jsonb)
                    RETURNING id::text, notice_type, status
                    """,
                    (nid, org_id, fields["notice_type"], fields["received_date"], fields.get("document_id"), "open", fields.get("ai_summary"), Json(fields.get("metadata") or {})),
                )
                return dict(cur.fetchone() or {"id": nid})

    def list(self, org_id: str, *, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id::text, notice_type, received_date::text, status, ai_summary FROM erp.tax_notices WHERE org_id=%s::uuid ORDER BY received_date DESC LIMIT %s",
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


tds_section_repository = TdsSectionRepository()
tds_transaction_repository = TdsTransactionRepository()
e_invoice_repository = EInvoiceRepository()
eway_bill_repository = EwayBillRepository()
compliance_calendar_repository = ComplianceCalendarRepository()
tax_notice_repository = TaxNoticeRepository()
