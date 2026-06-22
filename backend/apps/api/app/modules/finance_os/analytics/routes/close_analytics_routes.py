from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.finance_os.analytics.security.analytics_guard import require_analytics_read
from app.modules.finance_os.analytics.services.close_analytics_service import close_analytics_service

router = APIRouter(tags=["finance-os-analytics-close"])


@router.get("/close-analytics")
def close_analytics(
    fiscal_period_id: str | None = None,
    context=Depends(build_request_context),
) -> dict:
    require_analytics_read(context.user)
    item = close_analytics_service.get(context.org_id, fiscal_period_id=fiscal_period_id)
    return {"request_id": context.request_id, "item": item}
