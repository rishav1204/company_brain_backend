from __future__ import annotations

from app.modules.finance_os.forecasting.pipelines.forecast_refresh_pipeline import run_refresh


def run_forecast_refresh(org_id: str, *, trace_id: str | None = None) -> dict:
    return run_refresh(org_id, trace_id=trace_id)

