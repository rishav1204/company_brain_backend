from __future__ import annotations

from app.services.db import get_db_conn, set_rls_org


class TrialBalanceService:
    def generate(self, org_id: str, *, fiscal_period_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      COALESCE(SUM(debit_amount), 0)::numeric(18,2) AS debit_total,
                      COALESCE(SUM(credit_amount), 0)::numeric(18,2) AS credit_total
                    FROM erp.ledger_entries
                    WHERE org_id = %s::uuid AND fiscal_period_id = %s::uuid
                    """,
                    (org_id, fiscal_period_id),
                )
                totals = dict(cur.fetchone() or {"debit_total": 0, "credit_total": 0})

                cur.execute(
                    """
                    SELECT
                      le.account_id::text AS account_id,
                      a.code AS account_code,
                      a.name AS account_name,
                      COALESCE(SUM(le.debit_amount), 0)::numeric(18,2) AS debit_total,
                      COALESCE(SUM(le.credit_amount), 0)::numeric(18,2) AS credit_total
                    FROM erp.ledger_entries le
                    JOIN erp.chart_of_accounts a ON a.id = le.account_id
                    WHERE le.org_id = %s::uuid AND le.fiscal_period_id = %s::uuid
                    GROUP BY le.account_id, a.code, a.name
                    ORDER BY a.code ASC
                    """,
                    (org_id, fiscal_period_id),
                )
                lines = [dict(r) for r in (cur.fetchall() or [])]

        balanced = round(float(totals["debit_total"]) - float(totals["credit_total"]), 2) == 0
        return {"fiscal_period_id": fiscal_period_id, "totals": totals, "balanced": balanced, "lines": lines}


trial_balance_service = TrialBalanceService()

