from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ClaimRepository:
    def create(
        self,
        org_id: str,
        *,
        claim_number: str,
        employee_id: str,
        claim_date: str | None = None,
        expense_category: str | None = None,
        company_id: str | None = None,
        cost_center_id: str | None = None,
        department_id: str | None = None,
        created_by: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        cid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.expense_claims (
                      id, org_id, company_id, employee_id, claim_number, claim_date,
                      expense_category, cost_center_id, department_id, created_by, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,COALESCE(%s::date,CURRENT_DATE),
                            %s,%s::uuid,%s::uuid,%s::uuid,%s::jsonb)
                    RETURNING id::text, claim_number, status, total_amount
                    """,
                    (
                        cid, org_id, company_id, employee_id, claim_number, claim_date,
                        expense_category, cost_center_id, department_id, created_by, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": cid})

    def get(self, org_id: str, *, claim_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, employee_id::text, claim_number, claim_date::text, expense_category,
                           total_amount, status, workflow_approved, submitted_at::text, approved_at::text,
                           journal_id::text, reimbursement_payment_id::text, cost_center_id::text,
                           department_id::text, metadata, company_id::text, created_by::text,
                           approved_by::text, created_at::text
                    FROM erp.expense_claims
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, claim_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, employee_id: str | None = None, status: str | None = None, limit: int = 100) -> list[dict]:
        clauses = ["org_id = %s::uuid"]
        params: list = [org_id]
        if employee_id:
            clauses.append("employee_id = %s::uuid")
            params.append(employee_id)
        if status:
            clauses.append("status = %s")
            params.append(status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, claim_number, employee_id::text, claim_date::text, total_amount, status
                    FROM erp.expense_claims
                    WHERE {' AND '.join(clauses)}
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]

    def set_status(
        self,
        org_id: str,
        *,
        claim_id: str,
        status: str,
        workflow_approved: bool | None = None,
        approved_by: str | None = None,
        journal_id: str | None = None,
        reimbursement_payment_id: str | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.expense_claims
                    SET status = %s,
                        workflow_approved = COALESCE(%s, workflow_approved),
                        approved_by = COALESCE(%s::uuid, approved_by),
                        journal_id = COALESCE(%s::uuid, journal_id),
                        reimbursement_payment_id = COALESCE(%s::uuid, reimbursement_payment_id),
                        submitted_at = CASE WHEN %s = 'submitted' THEN NOW() ELSE submitted_at END,
                        approved_at = CASE WHEN %s = 'approved' THEN NOW() ELSE approved_at END,
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, workflow_approved, journal_id::text
                    """,
                    (
                        status, workflow_approved, approved_by, journal_id, reimbursement_payment_id,
                        status, status, org_id, claim_id,
                    ),
                )
                row = cur.fetchone()
                return dict(row) if row else {}

    def add_item(
        self,
        org_id: str,
        *,
        claim_id: str,
        expense_date: str,
        expense_type: str,
        amount: float,
        merchant_name: str | None = None,
        description: str | None = None,
        gst_amount: float = 0,
        receipt_id: str | None = None,
        expense_account_id: str | None = None,
    ) -> dict:
        iid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.expense_claim_items (
                      id, org_id, claim_id, expense_date, expense_type, merchant_name, description,
                      amount, gst_amount, receipt_id, expense_account_id
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::date,%s,%s,%s,%s::numeric,%s::numeric,%s::uuid,%s::uuid)
                    RETURNING id::text, expense_type, amount
                    """,
                    (
                        iid, org_id, claim_id, expense_date, expense_type, merchant_name, description,
                        amount, gst_amount, receipt_id, expense_account_id,
                    ),
                )
                item = dict(cur.fetchone() or {"id": iid})
                cur.execute(
                    """
                    UPDATE erp.expense_claims
                    SET total_amount = (SELECT COALESCE(SUM(amount + gst_amount), 0) FROM erp.expense_claim_items WHERE claim_id = %s::uuid),
                        updated_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (claim_id, claim_id),
                )
                return item

    def list_items(self, org_id: str, *, claim_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit, default=500, maximum=500)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, expense_date::text, expense_type, merchant_name, description,
                           amount, gst_amount, receipt_id::text, expense_account_id::text
                    FROM erp.expense_claim_items
                    WHERE org_id = %s::uuid AND claim_id = %s::uuid
                    ORDER BY expense_date
                    LIMIT %s
                    """,
                    (org_id, claim_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]


claim_repository = ClaimRepository()
