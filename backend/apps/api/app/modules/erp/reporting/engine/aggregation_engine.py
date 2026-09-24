from __future__ import annotations

from datetime import date

from app.modules.erp.accounts_payable.engine.aging_engine import bucket_invoice as bucket_ap_invoice
from app.modules.erp.accounts_receivable.engine.aging_engine import bucket_invoice as bucket_ar_invoice
from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository as ap_invoice_repository
from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository
from app.modules.erp.coa.repositories.mapping_repository import mapping_repository
from app.modules.erp.gl.repositories.balance_repository import balance_repository
from app.services.db import get_db_conn, set_rls_org

BUCKET_MAP = {
    "current": "bucket_current",
    "1-30": "bucket_1_30",
    "31-60": "bucket_31_60",
    "61-90": "bucket_61_90",
    "90+": "bucket_90_plus",
}


def aggregate_trial_balance(org_id: str, *, fiscal_period_id: str, company_id: str | None = None) -> list[dict]:
    balance_repository.recompute_period(org_id, fiscal_period_id=fiscal_period_id)
    company_clause = ""
    params: list = [org_id, fiscal_period_id]
    if company_id:
        company_clause = " AND (le.company_id = %s::uuid OR j.company_id = %s::uuid)"
        params.extend([company_id, company_id])
    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                  le.account_id::text AS account_id,
                  a.account_code AS account_code,
                  a.account_name AS account_name,
                  COALESCE(SUM(le.debit_amount), 0)::numeric(18,2) AS debit_total,
                  COALESCE(SUM(le.credit_amount), 0)::numeric(18,2) AS credit_total,
                  (COALESCE(SUM(le.debit_amount), 0) - COALESCE(SUM(le.credit_amount), 0))::numeric(18,2) AS balance
                FROM erp.ledger_entries le
                JOIN erp.chart_of_accounts a ON a.id = le.account_id
                LEFT JOIN erp.journals j ON j.id = le.journal_id
                WHERE le.org_id = %s::uuid AND le.fiscal_period_id = %s::uuid
                {company_clause}
                GROUP BY le.account_id, a.account_code, a.account_name
                ORDER BY a.account_code ASC
                """,
                tuple(params),
            )
            return [dict(r) for r in (cur.fetchall() or [])]


def aggregate_statement(
    org_id: str,
    *,
    fiscal_period_id: str,
    statement_type: str,
) -> list[dict]:
    mappings = mapping_repository.list_financial_mappings(org_id)
    stmt_maps = [m for m in mappings if str(m.get("statement_type")) == statement_type]
    balances = balance_repository.list_by_period(org_id, fiscal_period_id=fiscal_period_id, limit=5000)
    bal_by_account = {str(b.get("account_id")): float(b.get("closing_balance") or 0) for b in balances}
    rollups: dict[str, float] = {}
    for m in stmt_maps:
        acct = str(m.get("account_id"))
        cat = str(m.get("reporting_category") or "uncategorized")
        rollups[cat] = rollups.get(cat, 0.0) + bal_by_account.get(acct, 0.0)
    return [{"reporting_category": k, "amount": round(v, 2)} for k, v in sorted(rollups.items())]


def aggregate_ap_aging(org_id: str, *, as_of_date: str | None = None) -> list[dict]:
    as_of = (as_of_date or date.today().isoformat())[:10]
    outstanding = ap_invoice_repository.list_outstanding(org_id)
    by_vendor: dict[str, dict] = {}
    for inv in outstanding:
        item = bucket_ap_invoice(inv, as_of=as_of)
        vid = str(item.get("vendor_id") or item.get("id") or "unknown")
        row = by_vendor.setdefault(
            vid,
            {
                "entity_id": vid,
                "entity_name": item.get("vendor_name") or item.get("vendor_id"),
                "bucket_current": 0.0,
                "bucket_1_30": 0.0,
                "bucket_31_60": 0.0,
                "bucket_61_90": 0.0,
                "bucket_90_plus": 0.0,
                "total_outstanding": 0.0,
            },
        )
        col = BUCKET_MAP.get(str(item["bucket"]), "bucket_90_plus")
        amt = float(item["outstanding"])
        row[col] += amt
        row["total_outstanding"] += amt
    return list(by_vendor.values())


def aggregate_ar_aging(org_id: str, *, as_of_date: str | None = None) -> list[dict]:
    as_of = (as_of_date or date.today().isoformat())[:10]
    outstanding = ar_invoice_repository.list_outstanding(org_id)
    by_customer: dict[str, dict] = {}
    for inv in outstanding:
        item = bucket_ar_invoice(inv, as_of=as_of)
        cid = str(item.get("customer_id") or item.get("id") or "unknown")
        row = by_customer.setdefault(
            cid,
            {
                "entity_id": cid,
                "entity_name": item.get("customer_name") or item.get("customer_id"),
                "bucket_current": 0.0,
                "bucket_1_30": 0.0,
                "bucket_31_60": 0.0,
                "bucket_61_90": 0.0,
                "bucket_90_plus": 0.0,
                "total_outstanding": 0.0,
            },
        )
        col = BUCKET_MAP.get(str(item["bucket"]), "bucket_90_plus")
        amt = float(item["outstanding"])
        row[col] += amt
        row["total_outstanding"] += amt
    return list(by_customer.values())


def aggregate_gst_summary(org_id: str, *, return_period: str, return_type: str = "GSTR-3B") -> dict:
    from app.modules.erp.tax.services.gst_return_service import gst_return_service

    row = gst_return_service.generate_return(org_id, return_type=return_type, return_period=return_period)
    return row.get("payload") or {}


def aggregate_tds_summary(org_id: str, *, return_period: str, form_type: str = "26Q") -> dict:
    from app.modules.erp.tax.services.tds_return_service import tds_return_service

    row = tds_return_service.generate_return(org_id, form_type=form_type, return_period=return_period)
    return row.get("payload") or {}


def compute_forecast_variance(*, actual: float, forecast: float) -> float | None:
    from app.modules.erp.reporting.utils.variance import variance_percent

    if forecast == 0 and actual == 0:
        return 0.0
    if forecast == 0:
        return None
    return variance_percent(actual=actual, forecast=forecast)
