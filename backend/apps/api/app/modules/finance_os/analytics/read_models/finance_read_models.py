from __future__ import annotations

from datetime import date

from app.modules.erp.query_services import fiscal_queries, reporting_queries


def load_finance(org_id: str, *, fiscal_period_id: str | None = None) -> dict:
    """Batch read from ERP reporting via query facades (Wave 1 ACL)."""
    if not reporting_queries.schema_ready():
        return {"ready": False}
    fp = fiscal_period_id
    if not fp:
        periods = fiscal_queries.list_periods(org_id, limit=1)
        if not periods:
            return {"ready": False}
        fp = str(periods[0].get("id"))

    pnl = reporting_queries.get_pnl(org_id, fiscal_period_id=fp, refresh_if_missing=True)
    ar = reporting_queries.get_ar_aging(org_id, refresh_if_missing=True)
    ap = reporting_queries.get_ap_aging(org_id, refresh_if_missing=True)
    meta = pnl.get("meta") or {}
    ar_totals = ar.get("totals") or {}
    ap_totals = ap.get("totals") or {}
    return {
        "ready": True,
        "fiscal_period_id": fp,
        "revenue": float(meta.get("revenue_total") or 0),
        "expense": float(meta.get("expense_total") or 0),
        "gross_profit": float(meta.get("gross_profit") or 0),
        "net_profit": float(meta.get("net_profit") or 0),
        "ar_outstanding": float(ar_totals.get("grand_total") or 0),
        "ap_outstanding": float(ap_totals.get("grand_total") or 0),
        "ar_bucket_90_plus": float(ar_totals.get("bucket_90_plus") or 0),
        "ar_totals": ar_totals,
        "ap_totals": ap_totals,
    }


def days_in_period(org_id: str, *, fiscal_period_id: str) -> int:
    period = fiscal_queries.get_period_row(org_id, period_id=fiscal_period_id)
    if not period:
        return 30
    try:
        start = date.fromisoformat(str(period.get("start_date"))[:10])
        end = date.fromisoformat(str(period.get("end_date"))[:10])
        return max((end - start).days + 1, 1)
    except Exception:
        return 30
