from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class CategoryRepository:
    def list_active(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, category_code, category_name, depreciation_method,
                           default_useful_life_months, default_salvage_percent
                    FROM erp.asset_categories
                    WHERE org_id = %s::uuid AND is_active = true
                    ORDER BY category_name
                    """,
                    (org_id,),
                )
                return [dict(r) for r in cur.fetchall()]

    def get(self, org_id: str, *, category_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, category_code, category_name, depreciation_method,
                           default_useful_life_months, default_salvage_percent
                    FROM erp.asset_categories
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, category_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None


class PolicyRepository:
    def get_active(self, org_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, capitalization_threshold, depreciation_frequency
                    FROM erp.asset_policies
                    WHERE org_id = %s::uuid AND is_active = true
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (org_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None


category_repository = CategoryRepository()
policy_repository = PolicyRepository()
