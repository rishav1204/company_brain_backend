from __future__ import annotations

from app.services.event_bus import event_bus


FORECAST_GENERATED = "forecast.generated"
FORECAST_UPDATED = "forecast.updated"
FORECAST_RISK_DETECTED = "forecast.risk.detected"
FORECAST_ACCURACY_CALCULATED = "forecast.accuracy.calculated"


def emit_forecast_generated(
    org_id: str,
    *,
    forecast_type: str,
    horizon_days: int,
    as_of_date: str,
    confidence: float,
    trace_id: str | None = None,
) -> None:
    event_bus.publish(
        event_type=FORECAST_GENERATED,
        org_id=org_id,
        source="finance_os.forecasting",
        trace_id=trace_id,
        payload={
            "forecast_type": forecast_type,
            "horizon_days": int(horizon_days),
            "as_of_date": as_of_date,
            "confidence": float(confidence),
        },
    )


def emit_forecast_accuracy_calculated(org_id: str, *, forecast_id: str, variance_percent: float, trace_id: str | None = None) -> None:
    event_bus.publish(
        event_type=FORECAST_ACCURACY_CALCULATED,
        org_id=org_id,
        source="finance_os.forecasting",
        trace_id=trace_id,
        payload={"forecast_id": forecast_id, "variance_percent": float(variance_percent)},
    )

