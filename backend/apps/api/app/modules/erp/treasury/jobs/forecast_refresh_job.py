from __future__ import annotations

from app.modules.erp.treasury.services.treasury_forecast_service import treasury_forecast_service


def run_forecast_refresh(org_id: str) -> dict:
    forecasts = treasury_forecast_service.refresh_all(org_id)
    return {"forecasts_saved": len(forecasts)}
