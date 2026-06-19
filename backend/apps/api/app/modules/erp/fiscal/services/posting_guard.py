from __future__ import annotations

from app.modules.erp.fiscal.exceptions import PeriodClosedError
from app.modules.erp.fiscal.services.posting_validation_service import posting_validation_service


def ensure_posting_allowed(org_id: str, posting_date: str, *, company_id: str | None = None) -> None:
    posting_validation_service.validate_period_open(org_id, posting_date, company_id=company_id)
