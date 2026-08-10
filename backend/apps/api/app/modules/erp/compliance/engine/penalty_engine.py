from __future__ import annotations

from datetime import date, datetime


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


def estimate_penalty(*, obligation: dict) -> dict:
    """Estimate statutory penalty exposure for overdue compliance obligations."""
    code = str(obligation.get("compliance_code") or obligation.get("obligation_type") or "").upper()
    days = _days_overdue(obligation)
    base_tax = float(obligation.get("tax_liability") or obligation.get("amount") or 0)
    penalty = 0.0
    interest = 0.0
    formula = "none"

    if days <= 0:
        return {
            "penalty_amount": 0.0,
            "interest_amount": 0.0,
            "formula": formula,
            "obligation_id": obligation.get("id"),
            "days_overdue": 0,
        }

    if code.startswith("GST") or "GSTR" in code:
        # Late fee: Rs 50/day CGST + Rs 50/day SGST (simplified single bucket)
        penalty = min(round(days * 100, 2), 5000.0)
        interest = round(base_tax * 0.18 * days / 365, 2) if base_tax > 0 else 0.0
        formula = "gst_late_fee_100_per_day_capped_5000_plus_18pct_interest"
    elif code.startswith("TDS") or "26Q" in code or "24Q" in code:
        penalty = round(days * 200, 2)
        interest = round(base_tax * 0.015 * max(1, days // 30), 2) if base_tax > 0 else 0.0
        formula = "tds_late_filing_200_per_day_plus_1_5pct_pm"
    else:
        penalty = round(days * 50, 2)
        interest = round(base_tax * 0.12 * days / 365, 2) if base_tax > 0 else 0.0
        formula = "generic_50_per_day_plus_12pct_interest"

    return {
        "penalty_amount": round(penalty, 2),
        "interest_amount": round(interest, 2),
        "formula": formula,
        "obligation_id": obligation.get("id"),
        "days_overdue": days,
    }
