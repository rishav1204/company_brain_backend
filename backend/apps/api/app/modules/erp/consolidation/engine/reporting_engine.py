from __future__ import annotations

from typing import Any

from app.services.db import get_db_conn, set_rls_org


def aggregate_entity_trial_balance(
    org_id: str,
    *,
    fiscal_period_id: str,
    company_id: str,
) -> list[dict[str, Any]]:
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  le.account_id::text AS account_id,
                  a.code AS account_code,
                  a.name AS account_name,
                  COALESCE(SUM(le.debit_amount), 0)::numeric(18,2) AS debit_total,
                  COALESCE(SUM(le.credit_amount), 0)::numeric(18,2) AS credit_total,
                  (COALESCE(SUM(le.debit_amount), 0) - COALESCE(SUM(le.credit_amount), 0))::numeric(18,2) AS balance
                FROM erp.ledger_entries le
                JOIN erp.chart_of_accounts a ON a.id = le.account_id
                JOIN erp.journals j ON j.id = le.journal_id
                WHERE le.org_id = %s::uuid
                  AND le.fiscal_period_id = %s::uuid
                  AND (le.company_id = %s::uuid OR j.company_id = %s::uuid)
                GROUP BY le.account_id, a.code, a.name
                ORDER BY a.code ASC
                """,
                (org_id, fiscal_period_id, company_id, company_id),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def merge_trial_balances(balances_by_company: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for rows in balances_by_company:
        for row in rows:
            aid = str(row.get("account_id") or "")
            if not aid:
                continue
            if aid not in merged:
                merged[aid] = {
                    "account_id": aid,
                    "account_code": row.get("account_code"),
                    "account_name": row.get("account_name"),
                    "debit_total": 0.0,
                    "credit_total": 0.0,
                    "balance": 0.0,
                }
            merged[aid]["debit_total"] += float(row.get("debit_total") or 0)
            merged[aid]["credit_total"] += float(row.get("credit_total") or 0)
            merged[aid]["balance"] += float(row.get("balance") or 0)
    return sorted(merged.values(), key=lambda r: str(r.get("account_code") or ""))


def persist_consolidated_trial_balance(
    org_id: str,
    *,
    consolidation_run_id: str,
    group_company_id: str,
    fiscal_period_id: str,
    rows: list[dict[str, Any]],
) -> int:
    count = 0
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO erp_reporting.consolidated_trial_balance_mv (
                        org_id, consolidation_run_id, group_company_id, fiscal_period_id,
                        account_id, account_code, account_name,
                        debit_total, credit_total, balance
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s::uuid,
                        %s::uuid, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (org_id, consolidation_run_id, account_id)
                    DO UPDATE SET
                      debit_total = EXCLUDED.debit_total,
                      credit_total = EXCLUDED.credit_total,
                      balance = EXCLUDED.balance,
                      refreshed_at = now()
                    """,
                    (
                        org_id,
                        consolidation_run_id,
                        group_company_id,
                        fiscal_period_id,
                        row["account_id"],
                        row.get("account_code"),
                        row.get("account_name"),
                        row.get("debit_total", 0),
                        row.get("credit_total", 0),
                        row.get("balance", 0),
                    ),
                )
                count += 1
            conn.commit()
    return count


def branch_pnl(
    org_id: str,
    *,
    branch_id: str,
    fiscal_period_id: str,
) -> list[dict[str, Any]]:
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.code, a.name, a.account_type,
                       (COALESCE(SUM(le.debit_amount), 0) - COALESCE(SUM(le.credit_amount), 0))::numeric(18,2) AS net
                FROM erp.ledger_entries le
                JOIN erp.chart_of_accounts a ON a.id = le.account_id
                WHERE le.org_id = %s::uuid
                  AND le.fiscal_period_id = %s::uuid
                  AND le.branch_id = %s::uuid
                  AND a.account_type IN ('revenue', 'expense')
                GROUP BY a.code, a.name, a.account_type
                ORDER BY a.code
                """,
                (org_id, fiscal_period_id, branch_id),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
