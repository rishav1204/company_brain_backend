from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.finance_os.workflow_intelligence.schemas.workflow_intelligence_schema import RecommendationActionRequest
from app.modules.finance_os.workflow_intelligence.security.workflow_intelligence_guard import (
    require_workflow_intelligence_read,
    require_workflow_intelligence_write,
)
from app.modules.finance_os.workflow_intelligence.services.approval_optimization_service import approval_optimization_service

router = APIRouter(tags=["finance-os-workflow-intelligence"])


@router.get("/recommendations")
def list_recommendations(
    context=Depends(build_request_context),
    workflow_type: str | None = Query(default=None),
) -> dict:
    require_workflow_intelligence_read(context.user)
    return {"items": approval_optimization_service.list_open(str(context.org_id), workflow_type=workflow_type)}


@router.post("/recommendations/{recommendation_id}/accept")
def accept_recommendation(recommendation_id: str, context=Depends(build_request_context)) -> dict:
    require_workflow_intelligence_write(context.user)
    row = approval_optimization_service.accept(
        str(context.org_id), recommendation_id=recommendation_id, user_id=str(context.user_id)
    )
    return row or {}


@router.post("/recommendations/{recommendation_id}/reject")
def reject_recommendation(recommendation_id: str, context=Depends(build_request_context)) -> dict:
    require_workflow_intelligence_write(context.user)
    row = approval_optimization_service.reject(
        str(context.org_id), recommendation_id=recommendation_id, user_id=str(context.user_id)
    )
    return row or {}
