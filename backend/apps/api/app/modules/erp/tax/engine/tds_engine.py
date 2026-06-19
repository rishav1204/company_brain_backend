from __future__ import annotations

from datetime import date


def financial_year_from_date(value: str) -> str:
    dt = date.fromisoformat(str(value)[:10])
    if dt.month >= 4:
        return f"{dt.year}-{dt.year + 1}"
    return f"{dt.year - 1}-{dt.year}"


def quarter_from_date(value: str) -> str:
    dt = date.fromisoformat(str(value)[:10])
    if dt.month in (4, 5, 6):
        return "Q1"
    if dt.month in (7, 8, 9):
        return "Q2"
    if dt.month in (10, 11, 12):
        return "Q3"
    return "Q4"


def resolve_effective_rate(*, rate_pan: float, rate_no_pan: float, pan_present: bool) -> float:
    if pan_present:
        return float(rate_pan)
    return max(float(rate_no_pan), 20.0)


def calculate_tds(
    *,
    gross_amount: float,
    rate_pan: float,
    rate_no_pan: float,
    threshold: float,
    prior_ytd: float = 0,
    pan_present: bool = True,
) -> dict:
    if gross_amount <= 0:
        return {"tds_amount": 0.0, "net_amount": 0.0, "applicable": False, "rate": 0.0}
    rate = resolve_effective_rate(rate_pan=rate_pan, rate_no_pan=rate_no_pan, pan_present=pan_present)
    if threshold > 0 and (prior_ytd + gross_amount) < threshold:
        return {"tds_amount": 0.0, "net_amount": gross_amount, "applicable": False, "rate": rate}
    tds = round(gross_amount * rate / 100, 2)
    return {
        "tds_amount": tds,
        "net_amount": round(gross_amount - tds, 2),
        "applicable": True,
        "rate": rate,
        "pan_present": pan_present,
    }
