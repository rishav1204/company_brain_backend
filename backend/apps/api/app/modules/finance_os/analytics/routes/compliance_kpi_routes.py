from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.analytics.security.analytics_guard import require_analytics_read
from app.modules.finance_os.analytics.services.kpi_service import kpi_service

router = APIRouter(prefix="/compliance", tags=["finance-os-analytics-compliance"])


@router.get("/kpis")
def compliance_kpis(context=Depends(build_request_context)) -> dict:
    require_analytics_read(context.user)
    codes = ["compliance.filing_pct", "compliance.penalty_exposure"]
    items = kpi_service.list(context.org_id, kpi_codes=codes, limit=10)
    return {"request_id": context.request_id, "items": items}
