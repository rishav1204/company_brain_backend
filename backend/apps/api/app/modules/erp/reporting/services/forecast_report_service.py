from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import intelligence_registry
from app.modules.erp.reporting.utils.variance import variance_percent


class ForecastReportService:
    def get(
        self,
        org_id: str,
        *,
        forecast_type: str = "cash",
        horizon_days: int = 30,
        as_of_date: str | None = None,
    ) -> dict:
        forecast = intelligence_registry.forecast()
        data = forecast.get_series(
            org_id, forecast_type=forecast_type, horizon_days=horizon_days, as_of_date=as_of_date
        )
        variance_items = []
        for item in data.get("items") or []:
            forecast_val = float(item.get("forecast_value") or 0)
            actual_val = float(
                item.get("actual_value")
                or forecast.actual_proxy(org_id, forecast_type=forecast_type, forecast_val=forecast_val)
            )
            var = variance_percent(actual=actual_val, forecast=forecast_val)
            variance_items.append({**item, "actual_value": actual_val, "variance_percent": var})
        return {
            **data,
            "forecast_type": forecast_type,
            "variance": variance_items,
        }


forecast_report_service = ForecastReportService()
