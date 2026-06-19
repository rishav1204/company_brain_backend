from app.modules.erp.fiscal.exceptions import PeriodClosedError
from app.modules.erp.fiscal.services.posting_validation_service import PostingValidationService


def test_validate_open_period() -> None:
    svc = PostingValidationService()

    class FakeRepo:
        def find_for_date(self, org_id, *, posting_date, company_id=None):
            return {"id": "p1", "period_name": "May 2026", "lock_status": "open"}

    svc._repo = None
    import app.modules.erp.fiscal.services.posting_validation_service as mod

    original = mod.fiscal_period_repository
    mod.fiscal_period_repository = FakeRepo()
    try:
        row = svc.validate_period_open("org", "2026-05-15")
        assert row["id"] == "p1"
    finally:
        mod.fiscal_period_repository = original


def test_validate_closed_period_raises() -> None:
    svc = PostingValidationService()

    class FakeRepo:
        def find_for_date(self, org_id, *, posting_date, company_id=None):
            return {"id": "p1", "period_name": "May 2026", "lock_status": "closed"}

    import app.modules.erp.fiscal.services.posting_validation_service as mod

    original = mod.fiscal_period_repository
    mod.fiscal_period_repository = FakeRepo()
    try:
        try:
            svc.validate_period_open("org", "2026-05-15")
            assert False, "expected PeriodClosedError"
        except PeriodClosedError as exc:
            assert exc.code == "PERIOD_CLOSED"
            assert "May 2026" in exc.message
    finally:
        mod.fiscal_period_repository = original


def test_soft_lock_allows_privileged() -> None:
    svc = PostingValidationService()

    class FakeRepo:
        def find_for_date(self, org_id, *, posting_date, company_id=None):
            return {"id": "p1", "period_name": "May 2026", "lock_status": "soft_locked"}

    import app.modules.erp.fiscal.services.posting_validation_service as mod

    original = mod.fiscal_period_repository
    mod.fiscal_period_repository = FakeRepo()
    try:
        row = svc.validate_period(
            "org", "2026-05-15", roles=["cfo"], permissions=[]
        )
        assert row["lock_status"] == "soft_locked"
    finally:
        mod.fiscal_period_repository = original


def test_fy_code_april_march() -> None:
    from datetime import date

    from app.modules.erp.fiscal.services.fiscal_year_service import _fy_code

    assert _fy_code(date(2026, 4, 1)) == "FY2026-27"
