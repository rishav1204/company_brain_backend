from __future__ import annotations

from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository


def validate_period_dates(start_date: str, end_date: str) -> None:
    if start_date > end_date:
        raise ValueError("start_date must be <= end_date")
