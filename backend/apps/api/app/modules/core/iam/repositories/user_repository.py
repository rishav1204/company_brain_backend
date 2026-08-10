from typing import Any

from app.services.db import get_db_conn, set_rls_org


class UserRepository:
    def get_by_email(self, email: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, email, display_name, status,
                           password_hash, mfa_enabled, phone, last_login_at,
                           idp_subject, idp_provider
                    FROM core.users
                    WHERE lower(email) = lower(%s)
                    LIMIT 1
                    """,
                    (email.strip(),),
                )
                return cur.fetchone()

    def get_login_bundle(
        self,
        email: str,
        *,
        org_id: str | None = None,
        org_slug: str | None = None,
    ) -> dict[str, Any] | None:
        """Single-connection login read: user, roles, permissions, policy rows.

        Prefer an explicit org scope (id or slug). When neither is provided,
        resolve by email only if the address maps to exactly one active user
        (the common UI path that only collects email + password). Duplicate
        memberships across orgs still require the caller to supply org_id or
        org_slug (SEC-06).
        """
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                if org_id:
                    cur.execute(
                        """
                        SELECT id::text AS id, org_id::text AS org_id, email, display_name, status,
                               password_hash, mfa_enabled, phone, last_login_at,
                               idp_subject, idp_provider
                        FROM core.users
                        WHERE lower(email) = lower(%s) AND org_id = %s::uuid
                        LIMIT 1
                        """,
                        (email.strip(), org_id),
                    )
                    user = cur.fetchone()
                elif org_slug:
                    cur.execute(
                        """
                        SELECT u.id::text AS id, u.org_id::text AS org_id, u.email, u.display_name, u.status,
                               u.password_hash, u.mfa_enabled, u.phone, u.last_login_at,
                               u.idp_subject, u.idp_provider
                        FROM core.users u
                        JOIN core.organizations o ON o.id = u.org_id
                        WHERE lower(u.email) = lower(%s) AND lower(o.slug) = lower(%s)
                        LIMIT 1
                        """,
                        (email.strip(), org_slug.strip()),
                    )
                    user = cur.fetchone()
                else:
                    # Fetch up to 2 matches so we can distinguish unique vs ambiguous
                    # without loading every membership for a popular shared address.
                    cur.execute(
                        """
                        SELECT id::text AS id, org_id::text AS org_id, email, display_name, status,
                               password_hash, mfa_enabled, phone, last_login_at,
                               idp_subject, idp_provider
                        FROM core.users
                        WHERE lower(email) = lower(%s)
                        ORDER BY created_at ASC
                        LIMIT 2
                        """,
                        (email.strip(),),
                    )
                    matches = list(cur.fetchall())
                    if len(matches) == 0:
                        return None
                    if len(matches) > 1:
                        return {"ambiguous": True, "match_count": len(matches)}
                    user = matches[0]
                if not user:
                    return None
                org_id = user["org_id"]
                user_id = user["id"]
                cur.execute(
                    """
                    SELECT r.id::text AS role_id, r.name AS role_name, r.policy_context,
                           ur.company_id::text AS company_id, ur.branch_id::text AS branch_id,
                           ur.department_id::text AS department_id
                    FROM core.user_roles ur
                    JOIN core.roles r ON r.id = ur.role_id
                    WHERE ur.org_id = %s::uuid AND ur.user_id = %s::uuid
                    """,
                    (org_id, user_id),
                )
                role_rows = list(cur.fetchall())
                cur.execute(
                    """
                    SELECT DISTINCT p.permission_key
                    FROM core.user_roles ur
                    JOIN core.role_permissions rp ON rp.role_id = ur.role_id
                    JOIN core.permissions p ON p.id = rp.permission_id
                    WHERE ur.org_id = %s::uuid AND ur.user_id = %s::uuid
                    ORDER BY p.permission_key
                    """,
                    (org_id, user_id),
                )
                permissions = [str(row["permission_key"]) for row in cur.fetchall() if row.get("permission_key")]
        roles = [str(row["role_name"]) for row in role_rows if row.get("role_name")]
        return {
            "user": user,
            "roles": roles,
            "permissions": permissions,
            "role_rows": role_rows,
        }

    def get_by_id(self, org_id: str, user_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, email, display_name, status,
                           mfa_enabled, phone, last_login_at, created_at,
                           idp_subject, idp_provider
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

    def get_by_idp_subject(self, idp_provider: str, idp_subject: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, email, display_name, status,
                           mfa_enabled, phone, idp_subject, idp_provider
                    FROM core.users
                    WHERE idp_provider = %s AND idp_subject = %s
                    LIMIT 1
                    """,
                    (idp_provider, idp_subject),
                )
                return cur.fetchone()

    def link_idp_subject(self, org_id: str, user_id: str, idp_provider: str, idp_subject: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE core.users
                    SET idp_provider = %s, idp_subject = %s, updated_at = NOW()
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    """,
                    (idp_provider, idp_subject, user_id, org_id),
                )

    def update_password(self, org_id: str, user_id: str, password_hash: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT password_hash FROM core.users WHERE id = %s::uuid AND org_id = %s::uuid",
                    (user_id, org_id),
                )
                row = cur.fetchone()
                if row and row.get("password_hash"):
                    cur.execute(
                        "INSERT INTO core.password_history (user_id, password_hash) VALUES (%s::uuid, %s)",
                        (user_id, row["password_hash"]),
                    )
                cur.execute(
                    "UPDATE core.users SET password_hash = %s, updated_at = NOW() WHERE id = %s::uuid",
                    (password_hash, user_id),
                )

    def password_in_history(self, user_id: str, password_hash: str, limit: int = 5) -> bool:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM core.password_history
                    WHERE user_id = %s::uuid AND password_hash = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, password_hash, limit),
                )
                return cur.fetchone() is not None

    def create_reset_token(self, user_id: str, token_hash: str, expires_at) -> None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.password_reset_tokens (user_id, token_hash, expires_at)
                    VALUES (%s::uuid, %s, %s)
                    """,
                    (user_id, token_hash, expires_at),
                )

    def consume_reset_token(self, token_hash: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE core.password_reset_tokens
                    SET used_at = NOW()
                    WHERE token_hash = %s AND used_at IS NULL AND expires_at > NOW()
                    RETURNING user_id::text AS user_id
                    """,
                    (token_hash,),
                )
                return cur.fetchone()

    def assign_role(
        self,
        org_id: str,
        user_id: str,
        role_id: str,
        company_id: str | None = None,
        branch_id: str | None = None,
        department_id: str | None = None,
    ) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.user_roles (org_id, user_id, role_id, company_id, branch_id, department_id)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::uuid)
                    ON CONFLICT (user_id, role_id) DO UPDATE SET
                        company_id = EXCLUDED.company_id,
                        branch_id = EXCLUDED.branch_id,
                        department_id = EXCLUDED.department_id
                    """,
                    (org_id, user_id, role_id, company_id, branch_id, department_id),
                )
