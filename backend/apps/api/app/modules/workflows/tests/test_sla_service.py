from datetime import datetime, timezone

from app.modules.workflows.services.sla_service import add_business_hours, compute_sla_due_at, is_sla_breached


def test_add_business_hours_skips_weekend() -> None:
    # Friday 17:00 UTC + 4 business hours -> Monday 12:00 UTC
    start = datetime(2026, 5, 22, 17, 0, tzinfo=timezone.utc)
    due = add_business_hours(start, 4)
    assert due.weekday() == 0
    assert due.hour == 12


def test_sla_breach_detection() -> None:
    past = datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert is_sla_breached(past)
    assert not is_sla_breached(compute_sla_due_at(created_at=datetime.now(timezone.utc), sla_hours=48))
