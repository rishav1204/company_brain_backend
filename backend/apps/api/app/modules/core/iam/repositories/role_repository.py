from typing import Any

from app.services.db import get_db_conn, set_rls_org
from app.services.repository_pagination import clamp_limit


class RoleRepository:
    def list_roles(self, org_id: str, limit: int = 500) -> list[dict[str, Any]]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, name, description,
                           system_role, policy_context, created_at
                    FROM core.roles
                    WHERE org_id = %s::uuid
                    ORDER BY name
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return list(cur.fetchall())

    def get_role_by_name(self, org_id: str, name: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, name, description,
                           system_role, policy_context
                    FROM core.roles
                    WHERE org_id = %s::uuid AND lower(name) = lower(%s)
                    """,
                    (org_id, name),
                )
                return cur.fetchone()

    def list_users_by_role_name(self, org_id: str, role_name: str, limit: int = 50) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT u.id::text AS user_id, u.email, r.name AS role_name
                    FROM core.user_roles ur
                    JOIN core.roles r ON r.id = ur.role_id
                    JOIN core.users u ON u.id = ur.user_id
                    WHERE ur.org_id = %s::uuid AND lower(r.name) = lower(%s)
                    LIMIT %s
                    """,
                    (org_id, role_name, limit),
                )
                return list(cur.fetchall())

    def list_user_roles(self, org_id: str, user_id: str, limit: int = 500) -> list[dict[str, Any]]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT r.id::text AS role_id, r.name AS role_name, r.policy_context,
                           ur.company_id::text AS company_id, ur.branch_id::text AS branch_id,
                           ur.department_id::text AS department_id
                    FROM core.user_roles ur
                    JOIN core.roles r ON r.id = ur.role_id
                    WHERE ur.org_id = %s::uuid AND ur.user_id = %s::uuid
                    LIMIT %s
                    """,
                    (org_id, user_id, limit),
                )
                return list(cur.fetchall())

    def create_role(
        self,
        org_id: str,
        name: str,
        description: str | None = None,
        policy_context: dict | None = None,
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.roles (org_id, name, description, policy_context, system_role)
                    VALUES (%s::uuid, %s, %s, %s::jsonb, false)
                    RETURNING id::text AS id, org_id::text AS org_id, name, description, system_role, policy_context
                    """,
                    (org_id, name.strip(), description, policy_context or {}),
                )
                return cur.fetchone()

    def update_role(
        self,
        org_id: str,
        role_id: str,
        *,
        description: str | None = None,
        policy_context: dict | None = None,
    ) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        if description is not None:
            sets.append("description = %s")
            params.append(description)
        if policy_context is not None:
            sets.append("policy_context = %s::jsonb")
            params.append(policy_context)
        if not sets:
            return self.get_role_by_id(org_id, role_id)
        params.extend([role_id, org_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE core.roles SET {", ".join(sets)}, updated_at = NOW()
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text AS id, org_id::text AS org_id, name, description, system_role, policy_context
                    """,
                    tuple(params),
                )
                return cur.fetchone()

    def get_role_by_id(self, org_id: str, role_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, name, description,
                           system_role, policy_context
                    FROM core.roles
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    """,
                    (role_id, org_id),
                )
                return cur.fetchone()

    def remove_permission(self, org_id: str, role_id: str, permission_id: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM core.role_permissions rp
                    USING core.roles r
                    WHERE rp.role_id = r.id AND rp.role_id = %s::uuid AND rp.permission_id = %s::uuid
                      AND r.org_id = %s::uuid
                    """,
                    (role_id, permission_id, org_id),
                )

    def assign_permission(self, org_id: str, role_id: str, permission_id: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.role_permissions (role_id, permission_id)
                    SELECT %s::uuid, %s::uuid
                    FROM core.roles
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    ON CONFLICT DO NOTHING
                    """,
                    (role_id, permission_id, role_id, org_id),
                )
