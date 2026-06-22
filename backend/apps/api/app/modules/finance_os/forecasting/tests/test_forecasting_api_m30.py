from __future__ import annotations


def test_forecasting_router_prefix() -> None:
    from app.modules.finance_os.forecasting.events.forecast_events import FORECAST_GENERATED

    assert FORECAST_GENERATED == "forecast.generated"

