from __future__ import annotations


def validate_valuation_date(valuation_date: str) -> str:
    vdate = str(valuation_date)[:10]
    if len(vdate) < 10:
        raise ValueError("valuation_date must be YYYY-MM-DD")
    return vdate
