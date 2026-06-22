from datetime import date

from app.modules.erp.fiscal.services.fiscal_period_service import fiscal_period_service


def is_fiscal_period_open(org_id: str, company_id: str | None = None, period_key: str | None = None) -> bool:
    """Date-aware fiscal check against erp.fiscal_periods (canonical M12)."""
    if not org_id:
        return True
    posting_date = date.today().isoformat()
    if period_key and len(period_key) >= 7:
        posting_date = f"{period_key[:7]}-01"
    try:
        from app.modules.erp.fiscal.services.posting_validation_service import posting_validation_service

        return posting_validation_service.is_period_open_for_date(
            org_id, posting_date, company_id=company_id
        )
    except Exception:
        try:
            period = fiscal_period_service.resolve_open_period(
                org_id,
                posting_date=posting_date,
                company_id=company_id,
            )
            return bool(period)
        except Exception:
            return False
