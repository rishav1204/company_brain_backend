from __future__ import annotations

from datetime import date, datetime


def load_close(org_id: str, *, fiscal_period_id: str | None = None) -> dict:
    from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository
    from app.modules.finance_os.workflow_intelligence.services.workflow_pattern_service import workflow_pattern_service

    wf = workflow_pattern_service.analytics(org_id, workflow_type="PERIOD_CLOSE", days=90)
    period = None
    if fiscal_period_id:
        period = fiscal_period_repository.get(org_id, period_id=fiscal_period_id)
    else:
        periods = fiscal_period_repository.list(org_id, limit=5)
        for p in periods:
            if str(p.get("status")) == "closed" or p.get("closed_at"):
                period = p
                break
        if not period and periods:
            period = periods[0]

    duration_days = None
    if period and period.get("closed_at") and period.get("end_date"):
        try:
            end = date.fromisoformat(str(period.get("end_date"))[:10])
            closed = datetime.fromisoformat(str(period.get("closed_at")).replace("Z", "+00:00")).date()
            duration_days = max((closed - end).days, 0)
        except Exception:
            duration_days = None

    sla_breach = sum(1 for s in (wf.get("stage_stats") or []) if float(s.get("p95_seconds") or 0) > 86400 * 3)
    return {
        "fiscal_period_id": str(period.get("id")) if period else None,
        "close_duration_days": duration_days,
        "efficiency_score": float(wf.get("avg_efficiency_score") or 0),
        "sla_breach_count": sla_breach,
        "stage_stats": wf.get("stage_stats") or [],
        "period_status": period.get("status") if period else None,
    }
