from app.modules.erp.gl.services.fiscal_period_service import FiscalPeriodService


class _FakeRepo:
    def __init__(self, row: dict | None):
        self.row = row

    def find_open_for_date(self, *_args, **_kwargs):
        return self.row


def test_fiscal_resolve_open_period_allows_open_unlocked(monkeypatch) -> None:
    svc = FiscalPeriodService()
    fake = _FakeRepo({"id": "pid", "status": "open", "is_locked": False})
    monkeypatch.setattr("app.modules.erp.gl.services.fiscal_period_service.fiscal_period_repository", fake)
    assert svc.resolve_open_period("org", posting_date="2026-01-01")["id"] == "pid"


def test_fiscal_resolve_open_period_blocks_locked(monkeypatch) -> None:
    svc = FiscalPeriodService()
    fake = _FakeRepo({"id": "pid", "status": "open", "is_locked": True})
    monkeypatch.setattr("app.modules.erp.gl.services.fiscal_period_service.fiscal_period_repository", fake)
    try:
        svc.resolve_open_period("org", posting_date="2026-01-01")
        assert False, "expected error"
    except ValueError:
        assert True

