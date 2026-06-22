from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.finance_os.analytics.security.analytics_guard import require_analytics_read
from app.modules.finance_os.analytics.services.kpi_service import kpi_service

router = APIRouter(tags=["finance-os-analytics-kpis"])


@router.get("/kpis")
def list_kpis(
    codes: str | None = Query(None, description="Comma-separated KPI codes"),
    snapshot_date: str | None = None,
    limit: int = 100,
    context=Depends(build_request_context),
) -> dict:
    require_analytics_read(context.user)
    kpi_codes = [c.strip() for c in codes.split(",")] if codes else None
    items = kpi_service.list(context.org_id, kpi_codes=kpi_codes, snapshot_date=snapshot_date, limit=limit)
    return {"request_id": context.request_id, "items": items}
