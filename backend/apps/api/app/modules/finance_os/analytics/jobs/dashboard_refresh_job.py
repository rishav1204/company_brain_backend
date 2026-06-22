from __future__ import annotations

from app.modules.finance_os.analytics.pipelines.analytics_refresh_pipeline import run_refresh


def run_dashboard_refresh(org_id: str) -> dict:
    return run_refresh(org_id)
