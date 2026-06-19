from __future__ import annotations

from app.modules.erp.treasury.jobs.cash_snapshot_job import run_cash_snapshot
from app.modules.erp.treasury.jobs.forecast_refresh_job import run_forecast_refresh
from app.modules.erp.treasury.jobs.liquidity_monitor_job import run_liquidity_monitor


def run_treasury_daily(org_id: str) -> dict:
    snap = run_cash_snapshot(org_id)
    fc = run_forecast_refresh(org_id)
    liq = run_liquidity_monitor(org_id)
    return {"snapshot": snap, "forecast": fc, "liquidity": liq}
