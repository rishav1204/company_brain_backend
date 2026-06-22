from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.finance_os.analytics.schemas.analytics_schema import DashboardResponse
from app.modules.finance_os.analytics.security.analytics_guard import require_analytics_read
from app.modules.finance_os.analytics.services.executive_dashboard_service import executive_dashboard_service
from app.services.repositories import audit_repo

router = APIRouter(tags=["finance-os-analytics-dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def executive_dashboard(
    snapshot_date: str | None = None,
    context=Depends(build_request_context),
) -> DashboardResponse:
    require_analytics_read(context.user)
    data = executive_dashboard_service.get(context.org_id, snapshot_date=snapshot_date)
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="analytics.dashboard.viewed",
        object_ref=f"finance_os:analytics:dashboard:{data.get('snapshot_date')}",
    )
    return DashboardResponse(
        snapshot_date=data.get("snapshot_date"),
        refreshed_at=data.get("refreshed_at"),
        widgets=data.get("widgets") or {},
        trends=data.get("trends") or [],
        top_risks=data.get("top_risks") or [],
        top_opportunities=data.get("top_opportunities") or [],
        anomalies=data.get("anomalies") or [],
    )
