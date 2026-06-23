from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from app.services.db import get_db_conn, set_rls_org


class StatementMvRepository:
    def __init__(self, table: str) -> None:
        self._table = table

    def replace_period(self, org_id: str, *, fiscal_period_id: str, rows: list[dict]) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM erp_reporting.{self._table} WHERE org_id = %s::uuid AND fiscal_period_id = %s::uuid",
                    (org_id, fiscal_period_id),
                )
                count = 0
                for row in rows:
                    cur.execute(
                        f"""
                        INSERT INTO erp_reporting.{self._table} (
                          org_id, fiscal_period_id, reporting_category, amount, refreshed_at
                        )
                        VALUES (%s::uuid, %s::uuid, %s, %s::numeric, now())
                        """,
                        (org_id, fiscal_period_id, row["reporting_category"], row.get("amount", 0)),
                    )
                    count += 1
                return count

    def list_period(self, org_id: str, *, fiscal_period_id: str, limit: int = 500) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT reporting_category, amount, refreshed_at::text
                    FROM erp_reporting.{self._table}
                    WHERE org_id = %s::uuid AND fiscal_period_id = %s::uuid
                    ORDER BY reporting_category ASC
                    LIMIT %s
                    """,
                    (org_id, fiscal_period_id),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


pnl_repository = StatementMvRepository("pnl_mv")
balance_sheet_repository = StatementMvRepository("balance_sheet_mv")
