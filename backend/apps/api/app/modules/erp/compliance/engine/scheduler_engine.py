from __future__ import annotations

from datetime import date

from app.modules.erp.compliance.engine.compliance_engine import refresh_status
from app.modules.erp.compliance.engine.due_date_engine import periods_for_generation


def generation_periods(*, months_ahead: int = 3, today: date | None = None) -> list[str]:
    today = today or date.today()
    return periods_for_generation(year=today.year, month=today.month, months_ahead=months_ahead)


def apply_status_refresh(obligation: dict, *, today: date | None = None) -> dict:
    today = today or date.today()
    due_raw = obligation.get("due_date")
    if not due_raw:
        return obligation
    due = date.fromisoformat(str(due_raw)[:10])
    new_status = refresh_status(due_date=due, status=str(obligation.get("status") or "upcoming"), today=today)
    obligation["status"] = new_status
    return obligation
