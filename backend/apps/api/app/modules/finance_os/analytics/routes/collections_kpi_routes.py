from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.analytics.security.analytics_guard import require_analytics_read
from app.modules.finance_os.analytics.services.kpi_service import kpi_service

router = APIRouter(prefix="/collections", tags=["finance-os-analytics-collections"])


@router.get("/kpis")
def collections_kpis(context=Depends(build_request_context)) -> dict:
    require_analytics_read(context.user)
    codes = ["collections.dso", "working_capital.net"]
    items = kpi_service.list(context.org_id, kpi_codes=codes, limit=10)
    return {"request_id": context.request_id, "items": items}
