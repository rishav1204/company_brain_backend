from typing import Any

from app.services.db import get_db_conn, set_rls_org


class PermissionRepository:
    def list_permissions(self) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, resource, action, permission_key, description
                    FROM core.permissions
                    ORDER BY resource, action
                    """
                )
                return list(cur.fetchall())

    def create_permission(
        self,
        resource: str,
        action: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        permission_key = f"{resource.strip().lower()}.{action.strip().lower()}"
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.permissions (resource, action, permission_key, description)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id::text AS id, resource, action, permission_key, description
                    """,
                    (resource.strip().lower(), action.strip().lower(), permission_key, description),
                )
                return cur.fetchone()

    def update_permission(
        self,
        permission_id: str,
        *,
        description: str | None = None,
    ) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE core.permissions SET description = %s
                    WHERE id = %s::uuid
                    RETURNING id::text AS id, resource, action, permission_key, description
                    """,
                    (description, permission_id),
                )
                return cur.fetchone()

    def get_by_id(self, permission_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, resource, action, permission_key, description
                    FROM core.permissions WHERE id = %s::uuid
                    """,
                    (permission_id,),
                )
                return cur.fetchone()

    def get_by_key(self, permission_key: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, resource, action, permission_key, description
                    FROM core.permissions
                    WHERE permission_key = %s
                    """,
                    (permission_key.strip().lower(),),
                )
                return cur.fetchone()

    def list_permissions_for_user(self, org_id: str, user_id: str) -> list[str]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT p.permission_key
                    FROM core.user_roles ur
                    JOIN core.role_permissions rp ON rp.role_id = ur.role_id
                    JOIN core.permissions p ON p.id = rp.permission_id
                    WHERE ur.org_id = %s::uuid AND ur.user_id = %s::uuid
                    ORDER BY 1
                    """,
                    (org_id, user_id),
                )
                rows = cur.fetchall()
                return [str(row["permission_key"]) for row in rows]
