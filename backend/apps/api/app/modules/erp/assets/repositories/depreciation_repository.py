from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class DepreciationRepository:
    def create(
        self,
        org_id: str,
        *,
        asset_id: str,
        depreciation_date: str,
        period_key: str,
        opening_book_value: float,
        depreciation_amount: float,
        closing_book_value: float,
        journal_id: str | None,
    ) -> dict:
        did = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.asset_depreciation (
                      id, org_id, asset_id, depreciation_date, period_key,
                      opening_book_value, depreciation_amount, closing_book_value, journal_id
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::date,%s,%s::numeric,%s::numeric,%s::numeric,%s::uuid)
                    RETURNING id::text, period_key
                    """,
                    (
                        did, org_id, asset_id, depreciation_date, period_key,
                        opening_book_value, depreciation_amount, closing_book_value, journal_id,
                    ),
                )
                return dict(cur.fetchone() or {"id": did})

    def exists_for_period(self, org_id: str, *, asset_id: str, period_key: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM erp.asset_depreciation
                    WHERE org_id = %s::uuid AND asset_id = %s::uuid AND period_key = %s LIMIT 1
                    """,
                    (org_id, asset_id, period_key),
                )
                return cur.fetchone() is not None

    def list_for_asset(self, org_id: str, *, asset_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit, default=500, maximum=500)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, depreciation_date::text, period_key, opening_book_value,
                           depreciation_amount, closing_book_value, journal_id::text
                    FROM erp.asset_depreciation
                    WHERE org_id = %s::uuid AND asset_id = %s::uuid
                    ORDER BY depreciation_date DESC
                    LIMIT %s
                    """,
                    (org_id, asset_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]


depreciation_repository = DepreciationRepository()
