from datetime import date
import re

from app.modules.erp.fiscal.services.fiscal_period_service import fiscal_period_service

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.I,
)


def is_fiscal_period_open(org_id: str, company_id: str | None = None, period_key: str | None = None) -> bool:
    """Date-aware fiscal check against erp.fiscal_periods (canonical M12)."""
    if not org_id or not _UUID_RE.match(str(org_id).strip()):
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
            return True
