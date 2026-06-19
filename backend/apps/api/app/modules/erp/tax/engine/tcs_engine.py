from __future__ import annotations


def calculate_tcs(
    *,
    gross_amount: float,
    rate_pan: float,
    rate_no_pan: float,
    threshold: float,
    prior_ytd: float = 0,
    pan_present: bool = True,
) -> dict:
    from app.modules.erp.tax.engine.tds_engine import resolve_effective_rate

    if gross_amount <= 0:
        return {"tcs_amount": 0.0, "total_collected": 0.0, "applicable": False, "rate": 0.0}
    rate = resolve_effective_rate(rate_pan=rate_pan, rate_no_pan=rate_no_pan, pan_present=pan_present)
    if threshold > 0 and (prior_ytd + gross_amount) < threshold:
        return {"tcs_amount": 0.0, "total_collected": gross_amount, "applicable": False, "rate": rate}
    tcs = round(gross_amount * rate / 100, 2)
    return {
        "tcs_amount": tcs,
        "total_collected": round(gross_amount + tcs, 2),
        "applicable": True,
        "rate": rate,
        "pan_present": pan_present,
    }
