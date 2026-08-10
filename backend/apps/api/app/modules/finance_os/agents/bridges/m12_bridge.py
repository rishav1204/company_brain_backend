from __future__ import annotations

from app.modules.erp.query_services import fiscal_queries


def period_context(org_id: str, period_id: str | None) -> dict:
    if not period_id:
        return {}
    try:
        period = fiscal_queries.get_period(org_id, period_id=period_id)
        return period or {"period_id": period_id}
    except Exception:
        return {"period_id": period_id}
