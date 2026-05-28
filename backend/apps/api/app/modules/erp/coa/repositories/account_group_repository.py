from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class AccountGroupRepository:
    def create(
        self,
        org_id: str,
        *,
        group_name: str,
        group_code: str,
        group_type: str,
        nature: str,
        parent_group_id: str | None = None,
        company_id: str | None = None,
    ) -> dict:
        gid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.account_groups (
                      id, org_id, company_id, group_name, group_code, parent_group_id, group_type, nature
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s::uuid, %s, %s)
                    RETURNING id::text, group_name, group_code, parent_group_id::text AS parent_group_id,
                              group_type, nature, created_at::text
                    """,
                    (gid, org_id, company_id, group_name, group_code, parent_group_id, group_type, nature),
                )
                return dict(cur.fetchone() or {"id": gid})

    def list(self, org_id: str, *, company_id: str | None = None, limit: int = 200) -> list[dict]:
        limit = max(1, min(int(limit or 200), 1000))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if company_id:
                    cur.execute(
                        """
                        SELECT id::text, group_name, group_code, parent_group_id::text AS parent_group_id,
                               group_type, nature, created_at::text
                        FROM erp.account_groups
                        WHERE org_id = %s::uuid AND company_id = %s::uuid
                        ORDER BY group_code ASC
                        LIMIT %s
                        """,
                        (org_id, company_id, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, group_name, group_code, parent_group_id::text AS parent_group_id,
                               group_type, nature, created_at::text
                        FROM erp.account_groups
                        WHERE org_id = %s::uuid AND company_id IS NULL
                        ORDER BY group_code ASC
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in (cur.fetchall() or [])]

    def get(self, org_id: str, *, group_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, group_name, group_code, parent_group_id::text AS parent_group_id,
                           group_type, nature, created_at::text
                    FROM erp.account_groups
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, group_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def update_name(self, org_id: str, *, group_id: str, group_name: str, parent_group_id: str | None) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.account_groups
                    SET group_name = %s,
                        parent_group_id = %s::uuid
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, group_name, group_code, parent_group_id::text AS parent_group_id, group_type, nature
                    """,
                    (group_name, parent_group_id, org_id, group_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {"id": group_id, "status": "not_found"}


account_group_repository = AccountGroupRepository()

