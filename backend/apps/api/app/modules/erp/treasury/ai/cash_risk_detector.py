from __future__ import annotations

from app.modules.erp.treasury.engine.risk_engine import detect_treasury_risks


def detect_cash_risks(*, forecast_balance: float, coverage_ratio: float, **kwargs) -> list[dict]:
    return detect_treasury_risks(forecast_balance=forecast_balance, coverage_ratio=coverage_ratio, **kwargs)
