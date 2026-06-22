from __future__ import annotations

from app.modules.finance_os.analytics.pipelines.analytics_refresh_pipeline import run_refresh


def run_kpi_refresh(org_id: str, *, fiscal_period_id: str | None = None) -> dict:
    return run_refresh(org_id, fiscal_period_id=fiscal_period_id)
