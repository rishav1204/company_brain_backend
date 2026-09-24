from __future__ import annotations

from datetime import date

from app.modules.platform.regulatory.services.regulatory_resolver import (
    RegulatoryConfigError,
    regulatory_resolver,
)


def financial_year_from_date(value: str, *, org_id: str | None = None) -> str:
    dt = date.fromisoformat(str(value)[:10])
    try:
        fy_start = int(
            regulatory_resolver.resolve_param_numeric(
                "calendar.fy_start_month", org_id=org_id, required=False, default=4
            )
        )
    except RegulatoryConfigError:
        fy_start = 4
    fy_start = max(1, min(12, fy_start))
    if dt.month >= fy_start:
        return f"{dt.year}-{dt.year + 1}"
    return f"{dt.year - 1}-{dt.year}"


def quarter_from_date(value: str, *, org_id: str | None = None) -> str:
    dt = date.fromisoformat(str(value)[:10])
    try:
        fy_start = int(
            regulatory_resolver.resolve_param_numeric(
                "calendar.fy_start_month", org_id=org_id, required=False, default=4
            )
        )
    except RegulatoryConfigError:
        fy_start = 4
    # Offset months into FY
    m = ((dt.month - fy_start) % 12) + 1
    if m in (1, 2, 3):
        return "Q1"
    if m in (4, 5, 6):
        return "Q2"
    if m in (7, 8, 9):
        return "Q3"
    return "Q4"


def resolve_effective_rate(
    *,
    rate_pan: float,
    rate_no_pan: float,
    pan_present: bool,
    org_id: str | None = None,
) -> float:
    if pan_present:
        return float(rate_pan)
    try:
        floor = regulatory_resolver.resolve_param_numeric(
            "tds.no_pan_floor_pct", org_id=org_id, required=True
        )
    except RegulatoryConfigError as exc:
        raise ValueError(str(exc)) from exc
    return max(float(rate_no_pan), float(floor))


def calculate_tds(
    *,
    gross_amount: float,
    rate_pan: float,
    rate_no_pan: float,
    threshold: float,
    prior_ytd: float = 0,
    pan_present: bool = True,
    org_id: str | None = None,
) -> dict:
    if gross_amount <= 0:
        return {"tds_amount": 0.0, "net_amount": 0.0, "applicable": False, "rate": 0.0}
    rate = resolve_effective_rate(
        rate_pan=rate_pan,
        rate_no_pan=rate_no_pan,
        pan_present=pan_present,
        org_id=org_id,
    )
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
