from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class FiscalPeriodRepository:
    def create(
        self,
        org_id: str,
        *,
        period_name: str,
        start_date: str,
        end_date: str,
        company_id: str | None = None,
    ) -> dict:
        pid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.fiscal_periods (id, org_id, company_id, period_name, start_date, end_date, status, is_locked)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s::date, %s::date, 'open', false)
                    RETURNING id::text, period_name, start_date::text, end_date::text, status, is_locked, created_at::text
                    """,
                    (pid, org_id, company_id, period_name, start_date, end_date),
                )
                return dict(cur.fetchone() or {"id": pid})

    def list(self, org_id: str, *, company_id: str | None = None, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit or 100), 500))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if company_id:
                    cur.execute(
                        """
                        SELECT id::text, period_name, start_date::text, end_date::text, status, is_locked, created_at::text
                        FROM erp.fiscal_periods
                        WHERE org_id = %s::uuid AND company_id = %s::uuid
                        ORDER BY start_date DESC
                        LIMIT %s
                        """,
                        (org_id, company_id, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, period_name, start_date::text, end_date::text, status, is_locked, created_at::text
                        FROM erp.fiscal_periods
                        WHERE org_id = %s::uuid AND company_id IS NULL
                        ORDER BY start_date DESC
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in (cur.fetchall() or [])]

    def find_open_for_date(self, org_id: str, *, posting_date: str, company_id: str | None = None) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if company_id:
                    cur.execute(
                        """
                        SELECT id::text, period_name, status, is_locked
                        FROM erp.fiscal_periods
                        WHERE org_id = %s::uuid AND company_id = %s::uuid
                          AND %s::date BETWEEN start_date AND end_date
                        LIMIT 1
                        """,
                        (org_id, company_id, posting_date),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, period_name, status, is_locked
                        FROM erp.fiscal_periods
                        WHERE org_id = %s::uuid AND company_id IS NULL
                          AND %s::date BETWEEN start_date AND end_date
                        LIMIT 1
                        """,
                        (org_id, posting_date),
                    )
                row = cur.fetchone()
                return dict(row) if row else None

    def set_status(self, org_id: str, *, fiscal_period_id: str, status: str, is_locked: bool) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.fiscal_periods
                    SET status = %s, is_locked = %s
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, is_locked
                    """,
                    (status, bool(is_locked), org_id, fiscal_period_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {"id": fiscal_period_id, "status": "not_found"}


fiscal_period_repository = FiscalPeriodRepository()

