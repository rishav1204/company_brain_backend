from __future__ import annotations

from app.modules.finance_os.forecasting.repositories.accuracy_repository import accuracy_repository


def variance_percent(*, actual: float, forecast: float) -> float:
    denom = abs(float(forecast)) if float(forecast) != 0 else 1.0
    return round((float(actual) - float(forecast)) / denom * 100.0, 2)


def record_accuracy(org_id: str, *, forecast_id: str, actual_value: float, forecast_value: float) -> dict:
    return accuracy_repository.create(
        org_id,
        forecast_id=forecast_id,
        actual_value=float(actual_value),
        forecast_value=float(forecast_value),
        variance_percent=variance_percent(actual=actual_value, forecast=forecast_value),
    )

