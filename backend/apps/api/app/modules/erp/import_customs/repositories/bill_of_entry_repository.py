from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class BillOfEntryRepository:
    def create(
        self,
        org_id: str,
        *,
        boe_number: str,
        boe_date: str,
        assessable_value: float,
        customs_duty: float,
        igst_import: float,
        company_id: str | None = None,
        branch_id: str | None = None,
        port_code: str | None = None,
        vendor_id: str | None = None,
        po_id: str | None = None,
        currency_code: str = "INR",
        exchange_rate: float = 1.0,
        metadata: dict | None = None,
    ) -> dict:
        bid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.bills_of_entry (
                      id, org_id, company_id, branch_id, boe_number, boe_date, port_code,
                      vendor_id, po_id, assessable_value, customs_duty, igst_import,
                      currency_code, exchange_rate, metadata
                    )
                    VALUES (
                      %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::date, %s,
                      %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s::jsonb
                    )
                    RETURNING id::text, boe_number, boe_date::text, status,
                              assessable_value::float8, customs_duty::float8, igst_import::float8,
                              company_id::text, branch_id::text, vendor_id::text, po_id::text,
                              currency_code, exchange_rate::float8, journal_id::text, created_at::text
                    """,
                    (
                        bid,
                        org_id,
                        company_id,
                        branch_id,
                        boe_number,
                        boe_date,
                        port_code,
                        vendor_id,
                        po_id,
                        assessable_value,
                        customs_duty,
                        igst_import,
                        currency_code,
                        exchange_rate,
                        Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": bid})

    def get(self, org_id: str, *, boe_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, boe_number, boe_date::text, status,
                           assessable_value::float8, customs_duty::float8, igst_import::float8,
                           company_id::text, branch_id::text, vendor_id::text, po_id::text,
                           port_code, currency_code, exchange_rate::float8,
                           journal_id::text, metadata, created_at::text
                    FROM erp.bills_of_entry
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, boe_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, status: str | None = None, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit or 100), 500))
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
                    SELECT id::text, boe_number, boe_date::text, status,
                           assessable_value::float8, customs_duty::float8, igst_import::float8,
                           company_id::text, vendor_id::text, journal_id::text, created_at::text
                    FROM erp.bills_of_entry
                    WHERE {' AND '.join(where)}
                    ORDER BY boe_date DESC, created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def set_posted(self, org_id: str, *, boe_id: str, journal_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.bills_of_entry
                    SET status = 'posted', journal_id = %s::uuid
                    WHERE org_id = %s::uuid AND id = %s::uuid AND status = 'draft'
                    RETURNING id::text, boe_number, status, journal_id::text
                    """,
                    (journal_id, org_id, boe_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None


bill_of_entry_repository = BillOfEntryRepository()
