from __future__ import annotations

from datetime import date

from app.modules.finance_os.analytics.engine import anomaly_engine, insight_engine, kpi_engine, trend_engine
from app.modules.finance_os.analytics.repositories.anomaly_flag_repository import anomaly_flag_repository
from app.modules.finance_os.analytics.repositories.insight_repository import insight_repository
from app.modules.finance_os.analytics.repositories.kpi_snapshot_repository import kpi_snapshot_repository
from app.modules.finance_os.analytics.repositories.kpi_trend_repository import kpi_trend_repository


def refresh_kpis(org_id: str, *, fiscal_period_id: str | None = None, snapshot_date: str | None = None) -> dict:
    snap = (snapshot_date or date.today().isoformat())[:10]
    prior_rows = kpi_snapshot_repository.list(org_id, snapshot_date=snap, limit=500)
    prior_by_code = {r["kpi_code"]: r for r in prior_rows}

    computed = kpi_engine.compute_all(org_id, fiscal_period_id=fiscal_period_id, snapshot_date=snap)
    saved = []
    for row in computed:
        saved.append(kpi_snapshot_repository.upsert(
            org_id,
            kpi_code=row["kpi_code"],
            kpi_value=float(row["kpi_value"]),
            snapshot_date=row["snapshot_date"],
            metadata=row.get("metadata"),
        ))

    trends_saved = []
    for row in computed:
        code = row["kpi_code"]
        history = kpi_snapshot_repository.history(org_id, kpi_code=code, limit=2)
        for t in trend_engine.compute_mom(history):
            trends_saved.append(kpi_trend_repository.upsert(
                org_id,
                kpi_code=code,
                trend_direction=t["trend_direction"],
                trend_percent=float(t["trend_percent"]),
                period_key=t["period_key"],
            ))

    prior_kpis = [{"kpi_code": c, "kpi_value": v.get("kpi_value")} for c, v in prior_by_code.items()]
    anomaly_flag_repository.clear_for_org(org_id)
    for flag in anomaly_engine.detect(computed, prior_kpis=prior_kpis):
        anomaly_flag_repository.create(org_id, **flag)

    insights_saved = []
    for ins in insight_engine.generate_insights(computed, prior_kpis=prior_kpis):
        insights_saved.append(insight_repository.create(org_id, **ins))

    return {"snapshot_date": snap, "kpis": len(saved), "trends": len(trends_saved), "insights": len(insights_saved)}
