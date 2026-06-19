from __future__ import annotations


def validate_year_end_ready(org_id: str, *, fiscal_year_id: str) -> None:
    from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository
    from app.modules.erp.fiscal.repositories.fiscal_year_repository import fiscal_year_repository

    fy = fiscal_year_repository.get(org_id, fiscal_year_id=fiscal_year_id)
    if not fy:
        raise ValueError("Fiscal year not found")
    periods = fiscal_period_repository.list(org_id, fiscal_year_id=fiscal_year_id, limit=20)
    if not periods:
        raise ValueError("No periods for fiscal year")
    open_periods = [p for p in periods if str(p.get("lock_status")) != "closed"]
    if open_periods:
        raise ValueError(f"{len(open_periods)} periods are not closed")
