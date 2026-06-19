from __future__ import annotations

from datetime import date, timedelta

from app.modules.erp.compliance.engine.due_date_engine import compute_due_date


def seed_obligations_for_period(*, year: int, month: int, rules: list[dict] | None = None) -> list[dict]:
    """Deprecated — use M21 obligation_service.generate_for_periods. Kept for tests importing legacy API."""
    period = f"{year:04d}-{month:02d}"
    if rules:
        items = []
        for rule in rules:
            due = compute_due_date(
                return_period=period,
                frequency=str(rule.get("frequency") or "monthly"),
                due_day=int(rule.get("due_day") or 1),
                month_offset=int(rule.get("month_offset") or 1),
            )
            items.append({
                "obligation_type": rule.get("compliance_code") or rule.get("obligation_type"),
                "due_date": due.isoformat(),
                "return_period": period,
                "status": "pending",
            })
        return items
    return []


def upcoming_deadlines(obligations: list[dict], *, within_days: int = 7) -> list[dict]:
    today = date.today()
    cutoff = today + timedelta(days=within_days)
    result = []
    for ob in obligations:
        try:
            due = date.fromisoformat(str(ob.get("due_date"))[:10])
        except ValueError:
            continue
        status = str(ob.get("status") or "pending")
        if today <= due <= cutoff and status in {"pending", "upcoming", "due_soon"}:
            result.append(ob)
    return result
