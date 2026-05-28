from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class AccountRepository:
    def create(
        self,
        org_id: str,
        *,
        account_code: str,
        account_name: str,
        account_type: str,
        group_id: str,
        parent_account_id: str | None,
        is_postable: bool,
        currency_code: str,
        company_id: str | None = None,
    ) -> dict:
        aid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.chart_of_accounts (
                      id, org_id, company_id, account_code, account_name, account_type, group_id,
                      parent_account_id, is_postable, currency_code
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::uuid, %s::uuid, %s, %s)
                    RETURNING id::text, account_code, account_name, account_type,
                              group_id::text AS group_id,
                              parent_account_id::text AS parent_account_id,
                              is_postable, is_active, currency_code,
                              created_at::text, updated_at::text
                    """,
                    (
                        aid,
                        org_id,
                        company_id,
                        account_code,
                        account_name,
                        account_type,
                        group_id,
                        parent_account_id,
                        bool(is_postable),
                        currency_code,
                    ),
                )
                return dict(cur.fetchone() or {"id": aid})

    def get(self, org_id: str, *, account_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, account_code, account_name, account_type,
                           group_id::text AS group_id,
                           parent_account_id::text AS parent_account_id,
                           is_postable, is_active, currency_code,
                           created_at::text, updated_at::text
                    FROM erp.chart_of_accounts
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, account_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, company_id: str | None = None, limit: int = 200) -> list[dict]:
        limit = max(1, min(int(limit or 200), 2000))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if company_id:
                    cur.execute(
                        """
                        SELECT id::text, account_code, account_name, account_type,
                               group_id::text AS group_id,
                               parent_account_id::text AS parent_account_id,
                               is_postable, is_active, currency_code,
                               created_at::text, updated_at::text
                        FROM erp.chart_of_accounts
                        WHERE org_id = %s::uuid AND company_id = %s::uuid
                        ORDER BY account_code ASC
                        LIMIT %s
                        """,
                        (org_id, company_id, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, account_code, account_name, account_type,
                               group_id::text AS group_id,
                               parent_account_id::text AS parent_account_id,
                               is_postable, is_active, currency_code,
                               created_at::text, updated_at::text
                        FROM erp.chart_of_accounts
                        WHERE org_id = %s::uuid AND company_id IS NULL
                        ORDER BY account_code ASC
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in (cur.fetchall() or [])]

    def deactivate(self, org_id: str, *, account_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.chart_of_accounts
                    SET is_active = FALSE, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, is_active, updated_at::text
                    """,
                    (org_id, account_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {"id": account_id, "status": "not_found"}

    def update_name_and_parent(self, org_id: str, *, account_id: str, account_name: str, parent_account_id: str | None) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.chart_of_accounts
                    SET account_name = %s,
                        parent_account_id = %s::uuid,
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, account_code, account_name, account_type,
                              group_id::text AS group_id,
                              parent_account_id::text AS parent_account_id,
                              is_postable, is_active, currency_code,
                              updated_at::text
                    """,
                    (account_name, parent_account_id, org_id, account_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {"id": account_id, "status": "not_found"}


account_repository = AccountRepository()

