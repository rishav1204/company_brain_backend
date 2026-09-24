from __future__ import annotations

from datetime import date, datetime

from app.modules.platform.regulatory.services.regulatory_resolver import (
    RegulatoryConfigError,
    regulatory_resolver,
)


def _days_overdue(obligation: dict) -> int:
    due = obligation.get("due_date") or obligation.get("filing_due_date")
    if not due:
        return 0
    try:
        due_d = datetime.fromisoformat(str(due)[:10]).date()
    except ValueError:
        return 0
    if str(obligation.get("status") or "").lower() in {"filed", "completed", "closed"}:
        return 0
    return max(0, (date.today() - due_d).days)


def estimate_penalty(*, obligation: dict, org_id: str | None = None) -> dict:
    """Estimate statutory penalty exposure using DB formula configuration."""
    code = str(obligation.get("compliance_code") or obligation.get("obligation_type") or "").upper()
    days = _days_overdue(obligation)
    base_tax = float(obligation.get("tax_liability") or obligation.get("amount") or 0)
    org = org_id or obligation.get("org_id")

    if days <= 0:
        return {
            "penalty_amount": 0.0,
            "interest_amount": 0.0,
            "formula": "none",
            "obligation_id": obligation.get("id"),
            "days_overdue": 0,
        }

    try:
        formula = regulatory_resolver.resolve_penalty_formula(code or "GENERIC", org_id=org)
    except RegulatoryConfigError as exc:
        raise ValueError(str(exc)) from exc

    daily = float(formula.get("daily_fee") or 0)
    is_nil = float(base_tax or 0) <= 0 and formula.get("nil_daily_fee") is not None
    if is_nil:
        daily = float(formula.get("nil_daily_fee") or daily)
    fee_cap = formula.get("fee_cap")
    turnover = float(obligation.get("aggregate_turnover") or obligation.get("turnover") or 0)
    caps = formula.get("cap_by_turnover_json") or []
    if isinstance(caps, list) and turnover > 0:
        for band in caps:
            if not isinstance(band, dict):
                continue
            max_t = band.get("max_turnover")
            if max_t is None or turnover <= float(max_t):
                if band.get("fee_cap") is not None:
                    fee_cap = band.get("fee_cap")
                break

    penalty = round(days * daily, 2)
    if fee_cap is not None:
        penalty = min(penalty, float(fee_cap))

    interest = 0.0
    annual = formula.get("interest_annual_pct")
    monthly = formula.get("interest_monthly_pct")
    if annual is not None and base_tax > 0:
        interest = round(base_tax * float(annual) / 100.0 * days / 365, 2)
    elif monthly is not None and base_tax > 0:
        months = max(1, days // 30)
        interest = round(base_tax * float(monthly) / 100.0 * months, 2)

    return {
        "penalty_amount": round(penalty, 2),
        "interest_amount": round(interest, 2),
        "formula": str(formula.get("formula_code") or "db"),
        "obligation_id": obligation.get("id"),
        "days_overdue": days,
    }
