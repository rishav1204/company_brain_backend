from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class CostCenterRepository:
    def create(
        self,
        org_id: str,
        *,
        cost_center_code: str,
        cost_center_name: str,
        parent_cost_center_id: str | None,
        company_id: str | None = None,
    ) -> dict:
        cid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.cost_centers (
                      id, org_id, company_id, cost_center_code, cost_center_name, parent_cost_center_id
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s::uuid)
                    RETURNING id::text, cost_center_code, cost_center_name,
                              parent_cost_center_id::text AS parent_cost_center_id,
                              is_active, created_at::text
                    """,
                    (cid, org_id, company_id, cost_center_code, cost_center_name, parent_cost_center_id),
                )
                return dict(cur.fetchone() or {"id": cid})

    def list(self, org_id: str, *, company_id: str | None = None, limit: int = 200) -> list[dict]:
        limit = max(1, min(int(limit or 200), 2000))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if company_id:
                    cur.execute(
                        """
                        SELECT id::text, cost_center_code, cost_center_name,
                               parent_cost_center_id::text AS parent_cost_center_id,
                               is_active, created_at::text
                        FROM erp.cost_centers
                        WHERE org_id = %s::uuid AND company_id = %s::uuid
                        ORDER BY cost_center_code ASC
                        LIMIT %s
                        """,
                        (org_id, company_id, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, cost_center_code, cost_center_name,
                               parent_cost_center_id::text AS parent_cost_center_id,
                               is_active, created_at::text
                        FROM erp.cost_centers
                        WHERE org_id = %s::uuid AND company_id IS NULL
                        ORDER BY cost_center_code ASC
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in (cur.fetchall() or [])]

    def deactivate(self, org_id: str, *, cost_center_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.cost_centers
                    SET is_active = FALSE
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, is_active, created_at::text
                    """,
                    (org_id, cost_center_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {"id": cost_center_id, "status": "not_found"}

    def update_name_and_parent(
        self, org_id: str, *, cost_center_id: str, cost_center_name: str, parent_cost_center_id: str | None
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.cost_centers
                    SET cost_center_name = %s,
                        parent_cost_center_id = %s::uuid
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, cost_center_code, cost_center_name,
                              parent_cost_center_id::text AS parent_cost_center_id,
                              is_active, created_at::text
                    """,
                    (cost_center_name, parent_cost_center_id, org_id, cost_center_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {"id": cost_center_id, "status": "not_found"}


cost_center_repository = CostCenterRepository()

