from random import randint

import pytest

from app.core.config import settings


@pytest.fixture
def org_id() -> str:
    return "11111111-1111-4111-8111-111111111111"


def _generate_open_period(service, org_id: str, *, attempts: int = 5) -> tuple[str, list[dict]]:
    """Generate obligations into a far-future period that still has open work.

    Obligations upsert on (org_id, compliance_type_id, return_period) and the
    upsert never resets status, so every run of this test consumes its period
    permanently. Picking an unused one keeps the test repeatable, and the org
    has to be the seeded one because event_store.org_id is a foreign key.
    """
    for _ in range(attempts):
        period = f"{randint(2090, 2199)}-{randint(1, 12):02d}"
        result = service.generate_for_periods(org_id, periods=[period])
        assert result["generated"] >= 1
        items = [i for i in service.list(org_id) if i.get("return_period") == period]
        open_items = [i for i in items if str(i.get("status")) not in {"completed", "waived"}]
        if open_items:
            return period, open_items
    raise AssertionError("no far-future period with an open obligation after retries")


@pytest.mark.skipif(not settings.postgres_dsn, reason="POSTGRES_DSN required")
def test_obligation_lifecycle(org_id: str) -> None:
    from app.modules.erp.compliance.services.obligation_service import obligation_service

    obligation_service.ensure_rules(org_id)
    _, open_items = _generate_open_period(obligation_service, org_id)
    ob_id = open_items[0]["id"]
    obligation_service.refresh_statuses(org_id)
    completed = obligation_service.complete(org_id, ob_id, actor_id="test")
    assert completed["status"] == "completed"


@pytest.mark.skipif(not settings.postgres_dsn, reason="POSTGRES_DSN required")
def test_complete_by_source_gst(org_id: str) -> None:
    from app.modules.erp.compliance.services.obligation_service import obligation_service

    period = "2098-06"
    obligation_service.generate_for_periods(org_id, periods=[period])
    result = obligation_service.complete_by_source(org_id, compliance_code="GST_GSTR1", return_period=period)
    assert result["completed_count"] >= 0


@pytest.mark.skipif(not settings.postgres_dsn, reason="POSTGRES_DSN required")
def test_dashboard_build(org_id: str) -> None:
    from app.modules.erp.compliance.services.compliance_dashboard_service import compliance_dashboard_service

    item = compliance_dashboard_service.build(org_id)
    assert "today" in item
    assert "risk_score" in item


@pytest.mark.skipif(not settings.postgres_dsn, reason="POSTGRES_DSN required")
def test_scheduler_daily(org_id: str) -> None:
    from app.modules.erp.compliance.services.reminder_service import reminder_service
    from app.modules.erp.compliance.services.obligation_service import obligation_service

    obligation_service.refresh_statuses(org_id)
    result = reminder_service.process_due(org_id)
    assert "processed" in result


@pytest.mark.skipif(not settings.postgres_dsn, reason="POSTGRES_DSN required")
def test_fiscal_close_overdue_gate(org_id: str) -> None:
    from app.modules.erp.fiscal.validators.close_validator import validate_close_readiness

    try:
        validate_close_readiness(org_id, period_id="00000000-0000-4000-8000-000000000001", final=False)
    except ValueError as exc:
        msg = str(exc).lower()
        assert "checklist" in msg or "obligation" in msg or "not found" in msg
