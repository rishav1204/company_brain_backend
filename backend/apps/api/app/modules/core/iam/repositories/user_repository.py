from typing import Any

from app.services.db import get_db_conn, set_rls_org


class UserRepository:
    def get_by_email(self, email: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, email, display_name, status,
                           password_hash, mfa_enabled, phone, last_login_at
                    FROM core.users
                    WHERE lower(email) = lower(%s)
                    LIMIT 1
                    """,
                    (email.strip(),),
                )
                return cur.fetchone()

    def get_by_id(self, org_id: str, user_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, email, display_name, status,
                           mfa_enabled, phone, last_login_at, created_at
                    FROM core.users
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    """,
                    (user_id, org_id),
                )
                return cur.fetchone()

    def list_users(self, org_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, email, display_name, status,
                           mfa_enabled, phone, last_login_at, created_at
                    FROM core.users
                    WHERE org_id = %s::uuid
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (org_id, limit, offset),
                )
                return list(cur.fetchall())

    def create_user(
        self,
        org_id: str,
        email: str,
        display_name: str,
        password_hash: str,
        phone: str | None = None,
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.users (org_id, email, display_name, password_hash, phone, status)
                    VALUES (%s::uuid, %s, %s, %s, %s, 'active')
                    RETURNING id::text AS id, org_id::text AS org_id, email, display_name, status
                    """,
                    (org_id, email.strip().lower(), display_name, password_hash, phone),
                )
                return cur.fetchone()

    def update_last_login(self, user_id: str) -> None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE core.users SET last_login_at = NOW(), updated_at = NOW() WHERE id = %s::uuid",
                    (user_id,),
                )

    def update_status(self, org_id: str, user_id: str, status: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE core.users SET status = %s, updated_at = NOW()
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text AS id, org_id::text AS org_id, email, display_name, status
                    """,
                    (status, user_id, org_id),
                )
                return cur.fetchone()

    def assign_role(
        self,
        org_id: str,
        user_id: str,
        role_id: str,
        company_id: str | None = None,
        branch_id: str | None = None,
    ) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.user_roles (org_id, user_id, role_id, company_id, branch_id)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid)
                    ON CONFLICT (user_id, role_id) DO UPDATE SET
                        company_id = EXCLUDED.company_id,
                        branch_id = EXCLUDED.branch_id
                    """,
                    (org_id, user_id, role_id, company_id, branch_id),
                )
