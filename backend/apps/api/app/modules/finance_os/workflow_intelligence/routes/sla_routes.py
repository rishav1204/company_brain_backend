from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.finance_os.workflow_intelligence.repositories.prediction_repository import prediction_repository
from app.modules.finance_os.workflow_intelligence.schemas.workflow_intelligence_schema import OverridePredictionRequest
from app.modules.finance_os.workflow_intelligence.security.workflow_intelligence_guard import (
    require_workflow_intelligence_read,
    require_workflow_intelligence_write,
)
from app.modules.finance_os.workflow_intelligence.services.sla_prediction_service import sla_prediction_service

router = APIRouter(tags=["finance-os-workflow-intelligence"])


@router.get("/sla-risks")
def list_sla_risks(context=Depends(build_request_context), limit: int = Query(default=50, le=200)) -> dict:
    require_workflow_intelligence_read(context.user)
    return {"items": sla_prediction_service.list_risks(str(context.org_id), limit=limit)}


@router.get("/predictions")
def list_predictions(
    context=Depends(build_request_context),
    workflow_instance_id: str = Query(...),
) -> dict:
    require_workflow_intelligence_read(context.user)
    return {
        "predictions": prediction_repository.list_for_instance(str(context.org_id), workflow_instance_id),
    }


@router.post("/override-prediction")
def override_prediction(body: OverridePredictionRequest, context=Depends(build_request_context)) -> dict:
    require_workflow_intelligence_write(context.user)
    row = prediction_repository.update(
        str(context.org_id),
        body.prediction_id,
        data={"predicted_value": body.predicted_value, "metadata": {"human_override": True}},
    )
    return row or {}
