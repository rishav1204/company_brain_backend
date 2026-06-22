from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class ApprovalMatrixRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'governance' AND table_name = 'approval_matrix'
                        LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def list_active(
        self,
        org_id: str,
        *,
        action_code: str | None = None,
        department: str | None = None,
        company_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        clauses = ["org_id = %s::uuid", "is_active = TRUE"]
        params: list[Any] = [org_id]
        if action_code:
            clauses.append("action_code = %s")
            params.append(action_code)
        if department:
            clauses.append("(department IS NULL OR department = %s)")
            params.append(department)
        if company_id:
            clauses.append("(company_id IS NULL OR company_id = %s::uuid)")
            params.append(company_id)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, action_code, department, business_unit, company_id::text,
                           min_amount, max_amount, approver_role, level
                    FROM governance.approval_matrix
                    WHERE {' AND '.join(clauses)}
                    ORDER BY level ASC, min_amount ASC
                    """,
                    params,
                )
                return [dict(r) for r in cur.fetchall()]

    def upsert(
        self,
        org_id: str,
        *,
        action_code: str,
        approver_role: str,
        level: int = 1,
        min_amount: float = 0,
        max_amount: float | None = None,
        department: str | None = None,
        business_unit: str | None = None,
        company_id: str | None = None,
    ) -> dict[str, Any]:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO governance.approval_matrix (
                        id, org_id, action_code, department, business_unit, company_id,
                        min_amount, max_amount, approver_role, level
                    )
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::uuid, %s, %s, %s, %s)
                    RETURNING id::text, action_code, approver_role, level, min_amount, max_amount
                    """,
                    (
                        row_id,
                        org_id,
                        action_code,
                        department,
                        business_unit,
                        company_id,
                        min_amount,
                        max_amount,
                        approver_role,
                        level,
                    ),
                )
                return dict(cur.fetchone() or {})


approval_matrix_repository = ApprovalMatrixRepository()
