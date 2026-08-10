"""Pure reporting math — keeps ERP free of Finance OS imports for variance."""

from __future__ import annotations


def variance_percent(*, actual: float, forecast: float) -> float:
    denom = abs(float(forecast)) if float(forecast) != 0 else 1.0
    return round((float(actual) - float(forecast)) / denom * 100.0, 2)
