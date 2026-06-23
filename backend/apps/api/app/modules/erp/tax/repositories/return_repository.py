from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class GstReturnRepository:
    def create(self, org_id: str, **fields) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.gst_returns (id, org_id, return_type, return_period, status, payload, metadata)
                    VALUES (%s::uuid,%s::uuid,%s,%s,%s,%s::jsonb,%s::jsonb)
                    ON CONFLICT (org_id, return_type, return_period) DO UPDATE SET payload=EXCLUDED.payload, status='draft', updated_at=NOW()
                    RETURNING id::text, return_type, return_period, status
                    """,
                    (rid, org_id, fields["return_type"], fields["return_period"], "draft",
                     Json(fields.get("payload") or {}), Json(fields.get("metadata") or {})),
                )
                return dict(cur.fetchone() or {"id": rid})

    def get(self, org_id: str, *, return_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id::text, return_type, return_period, status, payload, workflow_approved, filed_at::text FROM erp.gst_returns WHERE org_id=%s::uuid AND id=%s::uuid",
                    (org_id, return_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, return_type: str | None = None, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if return_type:
            where.append("return_type = %s")
            params.append(return_type)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id::text, return_type, return_period, status, filed_at::text FROM erp.gst_returns WHERE {' AND '.join(where)} ORDER BY return_period DESC LIMIT %s",
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def set_status(self, org_id: str, *, return_id: str, status: str, **extra) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.gst_returns SET status=%s, workflow_approved=COALESCE(%s, workflow_approved),
                      filed_at=COALESCE(%s::timestamptz, filed_at), filed_by=COALESCE(%s::uuid, filed_by), updated_at=NOW()
                    WHERE org_id=%s::uuid AND id=%s::uuid
                    RETURNING id::text, status, return_type, return_period
                    """,
                    (status, extra.get("workflow_approved"), extra.get("filed_at"), extra.get("filed_by"), org_id, return_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("GST return not found")
                return dict(row)


class Gstr2bRepository:
    def bulk_insert(self, org_id: str, *, return_period: str, rows: list[dict]) -> int:
        count = 0
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                for row in rows:
                    cur.execute(
                        """
                        INSERT INTO erp.gstr2b_imports (id, org_id, return_period, vendor_gstin, invoice_ref, invoice_date, taxable_value, cgst_amount, sgst_amount, igst_amount, metadata)
                        VALUES (%s::uuid,%s::uuid,%s,%s,%s,%s::date,%s,%s,%s,%s,%s::jsonb)
                        """,
                        (
                            str(uuid4()), org_id, return_period, row.get("vendor_gstin"), row.get("invoice_ref"),
                            row.get("invoice_date"), row.get("taxable_value", 0), row.get("cgst_amount", 0),
                            row.get("sgst_amount", 0), row.get("igst_amount", 0), Json(row.get("metadata") or {}),
                        ),
                    )
                    count += 1
        return count

    def list(self, org_id: str, *, return_period: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id::text, vendor_gstin, invoice_ref, invoice_date::text, taxable_value, cgst_amount, sgst_amount, igst_amount FROM erp.gstr2b_imports WHERE org_id=%s::uuid AND return_period=%s ORDER BY invoice_date DESC LIMIT %s",
                    (org_id, return_period, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


class GstReconciliationRepository:
    def create(self, org_id: str, **fields) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.gst_reconciliations (id, org_id, gst_transaction_id, gstr2b_import_id, return_period, match_status, confidence_score, metadata)
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s::jsonb)
                    RETURNING id::text, match_status, confidence_score
                    """,
                    (
                        rid, org_id, fields.get("gst_transaction_id"), fields.get("gstr2b_import_id"),
                        fields["return_period"], fields.get("match_status", "pending"),
                        fields.get("confidence_score"), Json(fields.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": rid})

    def list(self, org_id: str, *, return_period: str | None = None, match_status: str | None = None, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if return_period:
            where.append("return_period = %s")
            params.append(return_period)
        if match_status:
            where.append("match_status = %s")
            params.append(match_status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT id::text, gst_transaction_id::text, gstr2b_import_id::text, return_period, match_status, confidence_score, metadata FROM erp.gst_reconciliations WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT %s",
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def resolve(self, org_id: str, *, reconciliation_id: str, status: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE erp.gst_reconciliations SET match_status=%s, updated_at=NOW() WHERE org_id=%s::uuid AND id=%s::uuid RETURNING id::text, match_status",
                    (status, org_id, reconciliation_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Reconciliation not found")
                return dict(row)


gst_return_repository = GstReturnRepository()
gstr2b_repository = Gstr2bRepository()
gst_reconciliation_repository = GstReconciliationRepository()
