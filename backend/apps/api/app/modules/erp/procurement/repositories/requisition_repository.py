from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class RequisitionRepository:
    def create(
        self,
        org_id: str,
        *,
        pr_number: str,
        requester_id: str | None = None,
        department_id: str | None = None,
        cost_center_id: str | None = None,
        required_date: str | None = None,
        description: str | None = None,
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
                    INSERT INTO erp.purchase_requisitions (
                      id, org_id, company_id, pr_number, requester_id, department_id,
                      cost_center_id, required_date, description, created_by, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s::uuid,%s::uuid,%s::uuid,%s::date,%s,%s::uuid,%s::jsonb)
                    RETURNING id::text, pr_number, status, total_amount, created_at::text
                    """,
                    (
                        rid, org_id, company_id, pr_number, requester_id, department_id,
                        cost_center_id, required_date, description, created_by, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": rid})

    def get(self, org_id: str, *, pr_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, pr_number, requester_id::text, department_id::text,
                           cost_center_id::text, status, workflow_approved, required_date::text,
                           total_amount, description, metadata, company_id::text,
                           created_by::text, approved_by::text, created_at::text, updated_at::text
                    FROM erp.purchase_requisitions
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, pr_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, status: str | None = None, limit: int = 100) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if status:
                    cur.execute(
                        """
                        SELECT id::text, pr_number, status, total_amount, required_date::text, created_at::text
                        FROM erp.purchase_requisitions
                        WHERE org_id = %s::uuid AND status = %s
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (org_id, status, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, pr_number, status, total_amount, required_date::text, created_at::text
                        FROM erp.purchase_requisitions
                        WHERE org_id = %s::uuid
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in cur.fetchall()]

    def set_status(
        self,
        org_id: str,
        *,
        pr_id: str,
        status: str,
        workflow_approved: bool | None = None,
        approved_by: str | None = None,
        total_amount: float | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.purchase_requisitions
                    SET status = %s,
                        workflow_approved = COALESCE(%s, workflow_approved),
                        approved_by = COALESCE(%s::uuid, approved_by),
                        total_amount = COALESCE(%s::numeric, total_amount),
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, pr_number, status, workflow_approved, total_amount
                    """,
                    (status, workflow_approved, approved_by, total_amount, org_id, pr_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {}

    def add_item(
        self,
        org_id: str,
        *,
        pr_id: str,
        item_name: str,
        quantity: float,
        unit_price: float,
        description: str | None = None,
        expense_account_id: str | None = None,
    ) -> dict:
        iid = str(uuid4())
        amount = round(quantity * unit_price, 2)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.purchase_requisition_items (
                      id, org_id, pr_id, item_name, description, quantity, unit_price, amount, expense_account_id
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s::numeric,%s::numeric,%s::numeric,%s::uuid)
                    RETURNING id::text, item_name, quantity, unit_price, amount
                    """,
                    (iid, org_id, pr_id, item_name, description, quantity, unit_price, amount, expense_account_id),
                )
                item = dict(cur.fetchone() or {"id": iid})
                cur.execute(
                    """
                    UPDATE erp.purchase_requisitions
                    SET total_amount = (
                      SELECT COALESCE(SUM(amount), 0) FROM erp.purchase_requisition_items WHERE pr_id = %s::uuid
                    ), updated_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (pr_id, pr_id),
                )
                return item

    def list_items(self, org_id: str, *, pr_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, item_name, description, quantity, unit_price, amount,
                           expense_account_id::text
                    FROM erp.purchase_requisition_items
                    WHERE org_id = %s::uuid AND pr_id = %s::uuid
                    ORDER BY created_at
                    """,
                    (org_id, pr_id),
                )
                return [dict(r) for r in cur.fetchall()]


requisition_repository = RequisitionRepository()
