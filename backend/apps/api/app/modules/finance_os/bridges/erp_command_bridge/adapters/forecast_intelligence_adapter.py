from __future__ import annotations

from app.modules.erp.ports.intelligence_registry import ForecastIntelligencePort


class ForecastIntelligenceAdapter:
    def get_series(
        self,
        org_id: str,
        *,
        forecast_type: str = "cash",
        horizon_days: int = 30,
        as_of_date: str | None = None,
    ) -> dict:
        from app.modules.finance_os.forecasting.services.forecast_query_service import get_series

        return get_series(
            org_id,
            forecast_type=forecast_type,
            horizon_days=horizon_days,
            as_of_date=as_of_date,
        )

    def actual_proxy(self, org_id: str, *, forecast_type: str, forecast_val: float) -> float:
        from app.modules.finance_os.forecasting.jobs.forecast_accuracy_job import _actual_proxy

        return _actual_proxy(org_id, forecast_type=forecast_type, forecast_val=forecast_val)


_: ForecastIntelligencePort | None = None
