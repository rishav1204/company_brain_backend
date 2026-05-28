from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.modules.workflows.middleware.workflow_permission_guard import require_workflow_permission
from app.modules.workflows.services.step_service import step_service
from app.modules.workflows.services.workflow_service import workflow_service

router = APIRouter(prefix="/workflows/steps", tags=["workflow-steps"])


class StepCompleteRequest(BaseModel):
    result: str = "completed"
    output: dict = Field(default_factory=dict)


@router.post("/{step_id}/complete")
def complete_workflow_step(
    step_id: str,
    request: StepCompleteRequest,
    context=Depends(require_workflow_permission("workflow.write", mode="write")),
) -> dict:
    if not workflow_service.schema_ready():
        raise HTTPException(status_code=503, detail="Workflow engine schema not ready")
    try:
        result = step_service.complete_step(
            org_id=context.org_id,
            step_id=step_id,
            actor_id=context.user_id,
            result=request.result,
            output=request.output,
            trace_id=context.request_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "request_id": context.request_id,
        "step_id": step_id,
        "workflow_status": result.get("status"),
        "verification_status": "step_completed",
    }
