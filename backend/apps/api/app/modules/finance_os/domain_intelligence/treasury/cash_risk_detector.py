from __future__ import annotations

from app.modules.erp.query_services import domain_calc


def detect_cash_risks(*, forecast_balance: float, coverage_ratio: float, **kwargs) -> list[dict]:
    return domain_calc.detect_treasury_risks(
        forecast_balance=forecast_balance,
        coverage_ratio=coverage_ratio,
        **kwargs,
    )
