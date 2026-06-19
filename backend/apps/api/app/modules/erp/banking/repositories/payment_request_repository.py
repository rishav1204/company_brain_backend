from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class PaymentRequestRepository:
    def create(
        self,
        org_id: str,
        *,
        payment_type: str,
        beneficiary_type: str,
        beneficiary_ref: str | None,
        bank_account_id: str,
        amount: float,
        currency_code: str,
        payment_reference: str,
        scheduled_date: str | None,
        source_type: str | None,
        source_id: str | None,
        company_id: str | None,
        created_by: str | None,
        metadata: dict | None = None,
    ) -> dict:
        pid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.payment_requests (
                      id, org_id, company_id, payment_type, beneficiary_type, beneficiary_ref,
                      bank_account_id, amount, currency_code, payment_reference, scheduled_date,
                      source_type, source_id, created_by, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s::uuid,%s::uuid,%s::numeric,%s,%s,%s::date,%s,%s::uuid,%s::uuid,%s::jsonb)
                    RETURNING id::text, payment_reference, status, approval_status, amount
                    """,
                    (
                        pid, org_id, company_id, payment_type, beneficiary_type, beneficiary_ref,
                        bank_account_id, amount, currency_code, payment_reference, scheduled_date,
                        source_type, source_id, created_by, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": pid})

    def get(self, org_id: str, *, payment_request_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, payment_type, beneficiary_type, beneficiary_ref::text,
                           bank_account_id::text, amount, currency_code, status, approval_status,
                           scheduled_date::text, source_type, source_id::text, payment_reference,
                           journal_id::text, metadata, created_by::text, approved_by::text, created_at::text
                    FROM erp.payment_requests
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, payment_request_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, status: str | None = None, limit: int = 200) -> list[dict]:
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
                    SELECT id::text, payment_type, amount, status, approval_status,
                           scheduled_date::text, payment_reference, bank_account_id::text
                    FROM erp.payment_requests
                    WHERE {' AND '.join(where)}
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def set_status(
        self,
        org_id: str,
        *,
        payment_request_id: str,
        status: str,
        approval_status: str | None = None,
        journal_id: str | None = None,
        approved_by: str | None = None,
    ) -> dict:
        fields = ["status = %s", "updated_at = NOW()"]
        params: list = [status]
        if approval_status is not None:
            fields.append("approval_status = %s")
            params.append(approval_status)
        if journal_id is not None:
            fields.append("journal_id = %s::uuid")
            params.append(journal_id)
        if approved_by is not None:
            fields.append("approved_by = %s::uuid")
            params.append(approved_by)
        params.extend([org_id, payment_request_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE erp.payment_requests SET {', '.join(fields)}
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, approval_status, journal_id::text
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Payment request not found")
                return dict(row)

    def update_metadata(self, org_id: str, *, payment_request_id: str, metadata: dict) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.payment_requests SET metadata = %s::jsonb, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, metadata
                    """,
                    (Json(metadata), org_id, payment_request_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Payment request not found")
                return dict(row)

    def find_duplicate(
        self,
        org_id: str,
        *,
        beneficiary_ref: str,
        amount: float,
        scheduled_date: str,
    ) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, payment_reference, status
                    FROM erp.payment_requests
                    WHERE org_id = %s::uuid AND beneficiary_ref = %s::uuid
                      AND amount = %s::numeric AND scheduled_date = %s::date
                      AND status NOT IN ('failed', 'cancelled')
                    LIMIT 1
                    """,
                    (org_id, beneficiary_ref, amount, scheduled_date),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def find_by_source(self, org_id: str, *, source_type: str, source_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, status, payment_reference
                    FROM erp.payment_requests
                    WHERE org_id = %s::uuid AND source_type = %s AND source_id = %s::uuid
                      AND status NOT IN ('failed', 'cancelled')
                    LIMIT 1
                    """,
                    (org_id, source_type, source_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def history_amounts_by_beneficiary(self, org_id: str, *, beneficiary_ref: str, limit: int = 10) -> list[float]:
        limit = max(1, min(limit, 50))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT amount FROM erp.payment_requests
                    WHERE org_id = %s::uuid AND beneficiary_ref = %s::uuid
                      AND status = 'completed'
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    (org_id, beneficiary_ref, limit),
                )
                return [float(r["amount"]) for r in (cur.fetchall() or [])]

    def list_by_types(self, org_id: str, *, payment_types: list[str], limit: int = 200) -> list[dict]:
        if not payment_types:
            return []
        limit = max(1, min(limit, 500))
        placeholders = ",".join(["%s"] * len(payment_types))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, payment_type, amount, status, scheduled_date::text, payment_reference
                    FROM erp.payment_requests
                    WHERE org_id = %s::uuid AND payment_type IN ({placeholders})
                      AND status IN ('approved', 'pending_approval', 'processing')
                    ORDER BY scheduled_date ASC NULLS LAST
                    LIMIT %s
                    """,
                    tuple([org_id, *payment_types, limit]),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def sum_upcoming(self, org_id: str, *, through_date: str) -> float:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(amount), 0) AS total
                    FROM erp.payment_requests
                    WHERE org_id = %s::uuid
                      AND status IN ('approved', 'pending_approval', 'processing')
                      AND scheduled_date IS NOT NULL AND scheduled_date <= %s::date
                    """,
                    (org_id, through_date),
                )
                row = cur.fetchone()
                return float((row or {}).get("total") or 0)


payment_request_repository = PaymentRequestRepository()
