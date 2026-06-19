from __future__ import annotations


def detect_treasury_risks(
    *,
    forecast_balance: float,
    coverage_ratio: float,
    upcoming_payroll: float = 0,
    upcoming_tax: float = 0,
    vendor_concentration_pct: float = 0,
) -> list[dict]:
    risks: list[dict] = []
    if forecast_balance < 0:
        risks.append({"type": "negative_cash_forecast", "severity": "high", "message": "Forecast projects negative cash balance"})
    if coverage_ratio < 1.0:
        risks.append({"type": "liquidity_risk", "severity": "high", "message": "Liquidity coverage below 1.0"})
    elif coverage_ratio < 1.5:
        risks.append({"type": "liquidity_monitor", "severity": "medium", "message": "Liquidity coverage in monitor band"})
    if upcoming_payroll > 0 and forecast_balance < upcoming_payroll:
        risks.append({"type": "payroll_risk", "severity": "high", "message": "Insufficient cash for upcoming payroll"})
    if upcoming_tax > 0 and forecast_balance < upcoming_tax:
        risks.append({"type": "tax_payment_risk", "severity": "high", "message": "Insufficient cash for upcoming tax obligations"})
    if vendor_concentration_pct > 40:
        risks.append({"type": "vendor_concentration", "severity": "medium", "message": f"Vendor concentration at {vendor_concentration_pct:.0f}%"})
    return risks


def coverage_health_band(ratio: float) -> str:
    if ratio > 1.5:
        return "healthy"
    if ratio >= 1.0:
        return "monitor"
    return "risk"
