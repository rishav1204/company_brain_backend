from app.modules.erp.gl.services.fiscal_period_service import FiscalPeriodService


def test_fiscal_resolve_open_period_allows_open_unlocked(monkeypatch) -> None:
    svc = FiscalPeriodService()

    def _resolve(*_a, **_k):
        return {"id": "pid"}

    monkeypatch.setattr(
        "app.modules.erp.gl.services.fiscal_period_service.erp_fiscal_period_service.resolve_open_period",
        _resolve,
    )
    assert svc.resolve_open_period("org", posting_date="2026-01-01")["id"] == "pid"


def test_fiscal_resolve_open_period_blocks_locked(monkeypatch) -> None:
    svc = FiscalPeriodService()

    def _resolve(*_a, **_k):
        raise ValueError("Fiscal period is not open")

    monkeypatch.setattr(
        "app.modules.erp.gl.services.fiscal_period_service.erp_fiscal_period_service.resolve_open_period",
        _resolve,
    )
    try:
        svc.resolve_open_period("org", posting_date="2026-01-01")
        assert False, "expected error"
    except ValueError:
        assert True
