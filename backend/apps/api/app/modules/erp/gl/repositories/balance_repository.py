from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class BalanceRepository:
    def list_by_period(self, org_id: str, *, fiscal_period_id: str, limit: int = 200) -> list[dict]:
        limit = max(1, min(int(limit or 200), 1000))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, account_id::text, fiscal_period_id::text,
                           debit_total, credit_total, closing_balance,
                           updated_at::text
                    FROM erp.account_balances
                    WHERE org_id = %s::uuid AND fiscal_period_id = %s::uuid
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (org_id, fiscal_period_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def recompute_period(self, org_id: str, *, fiscal_period_id: str) -> int:
        """
        Deterministic recompute from ledger_entries for a given fiscal period.
        """
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM erp.account_balances
                    WHERE org_id = %s::uuid AND fiscal_period_id = %s::uuid
                    """,
                    (org_id, fiscal_period_id),
                )
                cur.execute(
                    """
                    INSERT INTO erp.account_balances (id, org_id, account_id, fiscal_period_id, debit_total, credit_total, closing_balance, updated_at)
                    SELECT
                      gen_random_uuid(),
                      le.org_id,
                      le.account_id,
                      le.fiscal_period_id,
                      SUM(le.debit_amount)::numeric(18,2) AS debit_total,
                      SUM(le.credit_amount)::numeric(18,2) AS credit_total,
                      -- closing balance depends on account group nature
                      CASE
                        WHEN lower(ag.nature) = 'credit' THEN (SUM(le.credit_amount) - SUM(le.debit_amount))::numeric(18,2)
                        ELSE (SUM(le.debit_amount) - SUM(le.credit_amount))::numeric(18,2)
                      END AS closing_balance,
                      NOW()
                    FROM erp.ledger_entries le
                    JOIN erp.chart_of_accounts a ON a.id = le.account_id
                    JOIN erp.account_groups ag ON ag.id = a.group_id
                    WHERE le.org_id = %s::uuid AND le.fiscal_period_id = %s::uuid
                    GROUP BY le.org_id, le.account_id, le.fiscal_period_id, ag.nature
                    """,
                    (org_id, fiscal_period_id),
                )
                return int(cur.rowcount or 0)


balance_repository = BalanceRepository()

