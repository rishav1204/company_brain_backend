from __future__ import annotations

from app.services.db import get_db_conn, set_rls_org


class TrialBalanceRepository:
    def replace_period(self, org_id: str, *, fiscal_period_id: str, lines: list[dict]) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM erp_reporting.trial_balance_mv WHERE org_id = %s::uuid AND fiscal_period_id = %s::uuid",
                    (org_id, fiscal_period_id),
                )
                count = 0
                for line in lines:
                    cur.execute(
                        """
                        INSERT INTO erp_reporting.trial_balance_mv (
                          org_id, fiscal_period_id, account_id, account_code, account_name,
                          debit_total, credit_total, balance, refreshed_at
                        )
                        VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s::numeric, %s::numeric, %s::numeric, now())
                        """,
                        (
                            org_id,
                            fiscal_period_id,
                            line["account_id"],
                            line.get("account_code"),
                            line.get("account_name"),
                            line.get("debit_total", 0),
                            line.get("credit_total", 0),
                            line.get("balance", 0),
                        ),
                    )
                    count += 1
                return count

    def list_period(
        self,
        org_id: str,
        *,
        fiscal_period_id: str,
        cursor: str | None = None,
        limit: int = 100,
    ) -> tuple[list[dict], str | None]:
        limit = max(1, min(int(limit or 100), 500))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if cursor:
                    cur.execute(
                        """
                        SELECT account_id::text, account_code, account_name,
                               debit_total, credit_total, balance, refreshed_at::text
                        FROM erp_reporting.trial_balance_mv
                        WHERE org_id = %s::uuid AND fiscal_period_id = %s::uuid
                          AND account_code > %s
                        ORDER BY account_code ASC
                        LIMIT %s
                        """,
                        (org_id, fiscal_period_id, cursor, limit + 1),
                    )
                else:
                    cur.execute(
                        """
                        SELECT account_id::text, account_code, account_name,
                               debit_total, credit_total, balance, refreshed_at::text
                        FROM erp_reporting.trial_balance_mv
                        WHERE org_id = %s::uuid AND fiscal_period_id = %s::uuid
                        ORDER BY account_code ASC
                        LIMIT %s
                        """,
                        (org_id, fiscal_period_id, limit + 1),
                    )
                rows = [dict(r) for r in (cur.fetchall() or [])]
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = str(rows[-1].get("account_code") or "")
        return rows, next_cursor

    def totals(self, org_id: str, *, fiscal_period_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      COALESCE(SUM(debit_total), 0)::numeric(18,2) AS debit_total,
                      COALESCE(SUM(credit_total), 0)::numeric(18,2) AS credit_total,
                      MAX(refreshed_at)::text AS refreshed_at
                    FROM erp_reporting.trial_balance_mv
                    WHERE org_id = %s::uuid AND fiscal_period_id = %s::uuid
                    """,
                    (org_id, fiscal_period_id),
                )
                return dict(cur.fetchone() or {"debit_total": 0, "credit_total": 0, "refreshed_at": None})

    def has_data(self, org_id: str, *, fiscal_period_id: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM erp_reporting.trial_balance_mv
                    WHERE org_id = %s::uuid AND fiscal_period_id = %s::uuid LIMIT 1
                    """,
                    (org_id, fiscal_period_id),
                )
                return cur.fetchone() is not None


trial_balance_repository = TrialBalanceRepository()
