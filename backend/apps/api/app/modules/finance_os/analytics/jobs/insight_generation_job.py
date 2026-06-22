from __future__ import annotations

from app.modules.finance_os.analytics.engine import insight_engine
from app.modules.finance_os.analytics.repositories.insight_repository import insight_repository
from app.modules.finance_os.analytics.repositories.kpi_snapshot_repository import kpi_snapshot_repository


def run_insight_generation(org_id: str) -> dict:
    kpis = kpi_snapshot_repository.list(org_id, limit=50)
    if not kpis:
        return {"count": 0}
    insights = insight_engine.generate_insights(kpis)
    saved = [insight_repository.create(org_id, **ins) for ins in insights]
    return {"count": len(saved)}
