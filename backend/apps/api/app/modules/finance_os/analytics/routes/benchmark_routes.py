from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import build_request_context
from app.modules.finance_os.analytics.security.analytics_guard import require_analytics_read
from app.modules.finance_os.analytics.services.benchmark_service import benchmark_service
from app.modules.finance_os.analytics.services.trend_service import trend_service

router = APIRouter(tags=["finance-os-analytics-benchmarks"])


@router.get("/trends")
def list_trends(
    kpi_code: str | None = None,
    period: str | None = None,
    limit: int = 50,
    context=Depends(build_request_context),
) -> dict:
    require_analytics_read(context.user)
    items = trend_service.list(context.org_id, kpi_code=kpi_code, period=period, limit=limit)
    return {"request_id": context.request_id, "items": items}


@router.get("/benchmarks")
def benchmarks(
    kpi_code: str | None = Query(None, description="Optional KPI code; omit to list benchmarks for all KPIs"),
    limit: int = 50,
    context=Depends(build_request_context),
) -> dict:
    require_analytics_read(context.user)
    try:
        if kpi_code:
            item = benchmark_service.compare(context.org_id, kpi_code=kpi_code)
            return {"request_id": context.request_id, "item": item}
        items = benchmark_service.list(context.org_id, limit=limit)
        return {"request_id": context.request_id, "items": items}
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/insights")
def list_insights(
    severity: str | None = None,
    limit: int = 50,
    context=Depends(build_request_context),
) -> dict:
    require_analytics_read(context.user)
    from app.modules.finance_os.analytics.services.insight_service import insight_service

    items = insight_service.list(context.org_id, severity=severity, limit=limit)
    return {"request_id": context.request_id, "items": items}
