from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class PaymentRepository:
    def create(
        self,
        org_id: str,
        *,
        vendor_id: str,
        payment_reference: str,
        payment_date: str,
        amount: float,
        bank_account_id: str | None = None,
        company_id: str | None = None,
        created_by: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        pid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.ap_payments (
                      id, org_id, company_id, vendor_id, payment_reference, payment_date,
                      amount, bank_account_id, created_by, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s::date,%s::numeric,%s::uuid,%s::uuid,%s::jsonb)
                    RETURNING id::text, payment_reference, payment_date::text, amount, status, vendor_id::text
                    """,
                    (
                        pid, org_id, company_id, vendor_id, payment_reference,
                        payment_date, amount, bank_account_id, created_by, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": pid})

    def get(self, org_id: str, *, payment_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, vendor_id::text, payment_reference, payment_date::text,
                           amount, status, bank_account_id::text, journal_id::text,
                           created_by::text, metadata, created_at::text
                    FROM erp.ap_payments
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, payment_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def update_metadata(self, org_id: str, *, payment_id: str, metadata: dict) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.ap_payments
                    SET metadata = %s::jsonb, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, metadata, status
                    """,
                    (Json(metadata), org_id, payment_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Payment not found")
                return dict(row)

    def find_duplicate_schedule(
        self,
        org_id: str,
        *,
        vendor_id: str,
        payment_date: str,
        amount: float,
    ) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, payment_reference, status
                    FROM erp.ap_payments
                    WHERE org_id = %s::uuid AND vendor_id = %s::uuid
                      AND payment_date = %s::date AND amount = %s::numeric
                      AND status IN ('scheduled', 'processing', 'completed')
                    LIMIT 1
                    """,
                    (org_id, vendor_id, payment_date, amount),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def set_status(
        self,
        org_id: str,
        *,
        payment_id: str,
        status: str,
        journal_id: str | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.ap_payments
                    SET status = %s,
                        journal_id = COALESCE(%s::uuid, journal_id),
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, journal_id::text
                    """,
                    (status, journal_id, org_id, payment_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Payment not found")
                return dict(row)

    def add_allocation(self, org_id: str, *, payment_id: str, invoice_id: str, amount: float) -> dict:
        aid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.ap_payment_allocations (id, org_id, payment_id, invoice_id, amount)
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::numeric)
                    RETURNING id::text, payment_id::text, invoice_id::text, amount
                    """,
                    (aid, org_id, payment_id, invoice_id, amount),
                )
                return dict(cur.fetchone() or {"id": aid})

    def list(self, org_id: str, *, status: str | None = None, limit: int = 100) -> list[dict]:
        limit = max(1, min(limit, 500))
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
                    SELECT id::text, vendor_id::text, payment_reference, payment_date::text,
                           amount, status, journal_id::text, created_at::text
                    FROM erp.ap_payments
                    WHERE {' AND '.join(where)}
                    ORDER BY payment_date DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def link_voucher(self, org_id: str, *, payment_id: str, voucher_id: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.ap_payments SET voucher_id = %s::uuid, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (voucher_id, org_id, payment_id),
                )


payment_repository = PaymentRepository()
