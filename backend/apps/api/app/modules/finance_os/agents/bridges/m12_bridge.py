from __future__ import annotations


def period_context(org_id: str, period_id: str | None) -> dict:
    if not period_id:
        return {}
    try:
        from app.modules.erp.fiscal.services.fiscal_period_service import fiscal_period_service

        period = fiscal_period_service.get(org_id, period_id=period_id)
        return period or {"period_id": period_id}
    except Exception:
        return {"period_id": period_id}
