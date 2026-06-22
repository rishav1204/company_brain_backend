from __future__ import annotations


def trend_direction(pct: float, *, flat_threshold: float = 1.0) -> str:
    if pct > flat_threshold:
        return "up"
    if pct < -flat_threshold:
        return "down"
    return "flat"


def compute_trend_percent(current: float, prior: float) -> float:
    if prior == 0:
        return 0.0 if current == 0 else 100.0
    return round((current - prior) / abs(prior) * 100.0, 2)


def compute_mom(history: list[dict]) -> list[dict]:
    """history sorted newest first."""
    if len(history) < 2:
        return []
    current = history[0]
    prior = history[1]
    cur_val = float(current.get("kpi_value") or 0)
    pri_val = float(prior.get("kpi_value") or 0)
    pct = compute_trend_percent(cur_val, pri_val)
    return [{
        "kpi_code": current.get("kpi_code"),
        "trend_direction": trend_direction(pct),
        "trend_percent": pct,
        "period_key": "mom",
        "current": cur_val,
        "prior": pri_val,
    }]
