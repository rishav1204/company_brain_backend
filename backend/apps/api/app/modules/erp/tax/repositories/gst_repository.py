from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class GstRegistrationRepository:
    def create(self, org_id: str, **fields) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.gst_registrations
                      (id, org_id, gstin, legal_name, trade_name, state_code, registration_type, status)
                    VALUES (%s::uuid,%s::uuid,%s,%s,%s,%s,%s,%s)
                    RETURNING id::text, gstin, legal_name, state_code, status
                    """,
                    (rid, org_id, fields["gstin"], fields["legal_name"], fields.get("trade_name"),
                     fields["state_code"], fields.get("registration_type", "regular"), "active"),
                )
                return dict(cur.fetchone() or {"id": rid})

    def list(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id::text, gstin, legal_name, trade_name, state_code, registration_type, status, metadata FROM erp.gst_registrations WHERE org_id=%s::uuid ORDER BY created_at",
                    (org_id,),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def get_primary(self, org_id: str) -> dict | None:
        rows = self.list(org_id)
        return rows[0] if rows else None


class GstTransactionRepository:
    def create(self, org_id: str, **fields) -> dict:
        tid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.gst_transactions (
                      id, org_id, source_type, source_id, gst_type, taxable_value,
                      cgst_amount, sgst_amount, igst_amount, cess_amount, gst_rate,
                      invoice_date, party_gstin, place_of_supply, hsn_sac, return_period, metadata
                    ) VALUES (%s::uuid,%s::uuid,%s,%s::uuid,%s,%s,%s,%s,%s,%s,%s,%s::date,%s,%s,%s,%s,%s::jsonb)
                    ON CONFLICT (org_id, source_type, source_id, gst_type) DO UPDATE SET
                      taxable_value=EXCLUDED.taxable_value, cgst_amount=EXCLUDED.cgst_amount,
                      sgst_amount=EXCLUDED.sgst_amount, igst_amount=EXCLUDED.igst_amount,
                      return_period=EXCLUDED.return_period, metadata=EXCLUDED.metadata, invoice_date=EXCLUDED.invoice_date
                    RETURNING id::text, source_type, source_id, gst_type
                    """,
                    (
                        tid, org_id, fields["source_type"], fields["source_id"], fields["gst_type"],
                        fields.get("taxable_value", 0), fields.get("cgst_amount", 0), fields.get("sgst_amount", 0),
                        fields.get("igst_amount", 0), fields.get("cess_amount", 0), fields.get("gst_rate"),
                        fields["invoice_date"], fields.get("party_gstin"), fields.get("place_of_supply"),
                        fields.get("hsn_sac"), fields.get("return_period"), Json(fields.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": tid})

    def list(self, org_id: str, *, return_period: str | None = None, gst_type: str | None = None, limit: int = 500) -> list[dict]:
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if return_period:
            where.append("return_period = %s")
            params.append(return_period)
        if gst_type:
            where.append("gst_type = %s")
            params.append(gst_type)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, source_type, source_id::text, gst_type, taxable_value,
                           cgst_amount, sgst_amount, igst_amount, gst_rate, invoice_date::text,
                           party_gstin, place_of_supply, return_period, metadata
                    FROM erp.gst_transactions WHERE {' AND '.join(where)}
                    ORDER BY invoice_date DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def list_for_financial_year(self, org_id: str, *, financial_year: str, limit: int = 5000) -> list[dict]:
        """List transactions for FY (return_period prefix match, e.g. 2025-04 .. 2025-03 next year)."""
        fy = str(financial_year)[:4]
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, source_type, source_id::text, gst_type, taxable_value,
                           cgst_amount, sgst_amount, igst_amount, gst_rate, invoice_date::text,
                           party_gstin, place_of_supply, return_period, metadata
                    FROM erp.gst_transactions
                    WHERE org_id = %s::uuid AND return_period LIKE %s
                    ORDER BY invoice_date LIMIT %s
                    """,
                    (org_id, f"{fy}-%", limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def get_by_source(self, org_id: str, *, source_type: str, source_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id::text, gst_type, taxable_value, cgst_amount, sgst_amount, igst_amount FROM erp.gst_transactions WHERE org_id=%s::uuid AND source_type=%s AND source_id=%s::uuid",
                    (org_id, source_type, source_id),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


gst_registration_repository = GstRegistrationRepository()
gst_transaction_repository = GstTransactionRepository()
