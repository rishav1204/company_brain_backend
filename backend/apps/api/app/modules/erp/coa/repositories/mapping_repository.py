from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class MappingRepository:
    # Financial statement mappings
    def create_financial_mapping(
        self,
        org_id: str,
        *,
        account_id: str,
        statement_type: str,
        reporting_category: str,
        company_id: str | None = None,
    ) -> dict:
        mid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.financial_statement_mappings (
                      id, org_id, company_id, account_id, statement_type, reporting_category
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s)
                    RETURNING id::text, account_id::text AS account_id, statement_type, reporting_category, created_at::text
                    """,
                    (mid, org_id, company_id, account_id, statement_type, reporting_category),
                )
                return dict(cur.fetchone() or {"id": mid})

    def list_financial_mappings(self, org_id: str, *, company_id: str | None = None, limit: int = 200) -> list[dict]:
        limit = max(1, min(int(limit or 200), 2000))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if company_id:
                    cur.execute(
                        """
                        SELECT id::text, account_id::text AS account_id, statement_type, reporting_category, created_at::text
                        FROM erp.financial_statement_mappings
                        WHERE org_id = %s::uuid AND company_id = %s::uuid
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (org_id, company_id, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, account_id::text AS account_id, statement_type, reporting_category, created_at::text
                        FROM erp.financial_statement_mappings
                        WHERE org_id = %s::uuid AND company_id IS NULL
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in (cur.fetchall() or [])]

    def delete_financial_mapping(self, org_id: str, *, mapping_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM erp.financial_statement_mappings
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text
                    """,
                    (org_id, mapping_id),
                )
                row = cur.fetchone()
                return {"deleted": bool(row), "id": mapping_id}

    # GST mappings
    def create_gst_mapping(
        self,
        org_id: str,
        *,
        account_id: str,
        gst_type: str,
        itc_eligible: bool,
        company_id: str | None = None,
    ) -> dict:
        mid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.gst_account_mappings (
                      id, org_id, company_id, account_id, gst_type, itc_eligible
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s)
                    RETURNING id::text, account_id::text AS account_id, gst_type, itc_eligible, created_at::text
                    """,
                    (mid, org_id, company_id, account_id, gst_type, bool(itc_eligible)),
                )
                return dict(cur.fetchone() or {"id": mid})

    def list_gst_mappings(self, org_id: str, *, company_id: str | None = None, limit: int = 200) -> list[dict]:
        limit = max(1, min(int(limit or 200), 2000))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if company_id:
                    cur.execute(
                        """
                        SELECT id::text, account_id::text AS account_id, gst_type, itc_eligible, created_at::text
                        FROM erp.gst_account_mappings
                        WHERE org_id = %s::uuid AND company_id = %s::uuid
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (org_id, company_id, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, account_id::text AS account_id, gst_type, itc_eligible, created_at::text
                        FROM erp.gst_account_mappings
                        WHERE org_id = %s::uuid AND company_id IS NULL
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in (cur.fetchall() or [])]

    def delete_gst_mapping(self, org_id: str, *, mapping_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM erp.gst_account_mappings
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text
                    """,
                    (org_id, mapping_id),
                )
                row = cur.fetchone()
                return {"deleted": bool(row), "id": mapping_id}


mapping_repository = MappingRepository()

