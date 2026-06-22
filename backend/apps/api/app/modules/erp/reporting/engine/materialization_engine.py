from __future__ import annotations

from datetime import date

from app.modules.erp.reporting.engine import aggregation_engine
from app.modules.erp.reporting.repositories.aging_repository import ap_aging_repository, ar_aging_repository
from app.modules.erp.reporting.repositories.statement_repository import balance_sheet_repository, pnl_repository
from app.modules.erp.reporting.repositories.tax_summary_repository import gst_summary_repository, tds_summary_repository
from app.modules.erp.reporting.repositories.trial_balance_repository import trial_balance_repository


def refresh_trial_balance(org_id: str, *, fiscal_period_id: str) -> dict:
    lines = aggregation_engine.aggregate_trial_balance(org_id, fiscal_period_id=fiscal_period_id)
    count = trial_balance_repository.replace_period(org_id, fiscal_period_id=fiscal_period_id, lines=lines)
    return {"report": "trial_balance", "fiscal_period_id": fiscal_period_id, "lines": count}


def refresh_pnl(org_id: str, *, fiscal_period_id: str) -> dict:
    rows = aggregation_engine.aggregate_statement(org_id, fiscal_period_id=fiscal_period_id, statement_type="profit_loss")
    count = pnl_repository.replace_period(org_id, fiscal_period_id=fiscal_period_id, rows=rows)
    return {"report": "pnl", "fiscal_period_id": fiscal_period_id, "categories": count}


def refresh_balance_sheet(org_id: str, *, fiscal_period_id: str) -> dict:
    rows = aggregation_engine.aggregate_statement(
        org_id, fiscal_period_id=fiscal_period_id, statement_type="balance_sheet"
    )
    count = balance_sheet_repository.replace_period(org_id, fiscal_period_id=fiscal_period_id, rows=rows)
    return {"report": "balance_sheet", "fiscal_period_id": fiscal_period_id, "categories": count}


def refresh_ap_aging(org_id: str, *, as_of_date: str | None = None) -> dict:
    as_of = (as_of_date or date.today().isoformat())[:10]
    rows = aggregation_engine.aggregate_ap_aging(org_id, as_of_date=as_of)
    count = ap_aging_repository.replace_as_of(org_id, as_of_date=as_of, rows=rows)
    return {"report": "ap_aging", "as_of_date": as_of, "vendors": count}


def refresh_ar_aging(org_id: str, *, as_of_date: str | None = None) -> dict:
    as_of = (as_of_date or date.today().isoformat())[:10]
    rows = aggregation_engine.aggregate_ar_aging(org_id, as_of_date=as_of)
    count = ar_aging_repository.replace_as_of(org_id, as_of_date=as_of, rows=rows)
    return {"report": "ar_aging", "as_of_date": as_of, "customers": count}


def refresh_gst_summary(org_id: str, *, return_period: str, return_type: str = "GSTR-3B") -> dict:
    payload = aggregation_engine.aggregate_gst_summary(org_id, return_period=return_period, return_type=return_type)
    gst_summary_repository.upsert(org_id, return_period=return_period, type_value=return_type, payload=payload)
    return {"report": "gst", "return_period": return_period, "return_type": return_type}


def refresh_tds_summary(org_id: str, *, return_period: str, form_type: str = "26Q") -> dict:
    payload = aggregation_engine.aggregate_tds_summary(org_id, return_period=return_period, form_type=form_type)
    tds_summary_repository.upsert(org_id, return_period=return_period, type_value=form_type, payload=payload)
    return {"report": "tds", "return_period": return_period, "form_type": form_type}


def refresh_all_for_period(org_id: str, *, fiscal_period_id: str, as_of_date: str | None = None) -> dict:
    results = [
        refresh_trial_balance(org_id, fiscal_period_id=fiscal_period_id),
        refresh_pnl(org_id, fiscal_period_id=fiscal_period_id),
        refresh_balance_sheet(org_id, fiscal_period_id=fiscal_period_id),
        refresh_ap_aging(org_id, as_of_date=as_of_date),
        refresh_ar_aging(org_id, as_of_date=as_of_date),
    ]
    return {"fiscal_period_id": fiscal_period_id, "refreshed": results}
