from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from typing import Any
from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class HierarchyRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='erp' AND table_name='entity_hierarchy' LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def list_for_org(self, org_id: str, limit: int = 500) -> list[dict[str, Any]]:
        if not self.schema_ready():
            limit = clamp_limit(limit)
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, parent_company_id::text, child_company_id::text,
                           ownership_percent, effective_from::text, effective_to::text, created_at
                    FROM erp.entity_hierarchy
                    WHERE org_id = %s::uuid
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (org_id,),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def upsert(
        self,
        org_id: str,
        *,
        parent_company_id: str,
        child_company_id: str,
        ownership_percent: float,
        effective_from: str | None = None,
        effective_to: str | None = None,
    ) -> dict[str, Any]:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.entity_hierarchy (
                        id, org_id, parent_company_id, child_company_id,
                        ownership_percent, effective_from, effective_to
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s::date, %s::date)
                    ON CONFLICT (org_id, parent_company_id, child_company_id)
                    DO UPDATE SET ownership_percent = EXCLUDED.ownership_percent,
                                  effective_from = EXCLUDED.effective_from,
                                  effective_to = EXCLUDED.effective_to
                    RETURNING id::text, parent_company_id::text, child_company_id::text, ownership_percent
                    """,
                    (
                        row_id,
                        org_id,
                        parent_company_id,
                        child_company_id,
                        ownership_percent,
                        effective_from,
                        effective_to,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                return {
                    "id": row[0],
                    "parent_company_id": row[1],
                    "child_company_id": row[2],
                    "ownership_percent": float(row[3]),
                }

    def list_children(self, org_id: str, parent_company_id: str) -> list[dict[str, Any]]:
        rows = self.list_for_org(org_id)
        return [r for r in rows if r.get("parent_company_id") == parent_company_id]


hierarchy_repository = HierarchyRepository()
