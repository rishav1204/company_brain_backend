from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.workflows.middleware.workflow_permission_guard import require_workflow_permission
from app.modules.workflows.repositories import workflow_repo
from app.modules.workflows.schemas.workflow_schema import WorkflowDefinitionOut
from app.modules.workflows.services.workflow_service import workflow_service
from pydantic import BaseModel, Field

router = APIRouter(prefix="/workflows/definitions", tags=["workflow-definitions"])


class DefinitionCreateRequest(BaseModel):
    workflow_key: str
    name: str
    description: str | None = None
    definition_json: dict = Field(default_factory=dict)


@router.post("/")
def create_definition(
    request: DefinitionCreateRequest,
    context=Depends(require_workflow_permission("workflow.manage", mode="write")),
) -> dict:
    if not workflow_service.schema_ready():
        raise HTTPException(status_code=503, detail="Workflow engine schema not ready")
    row = workflow_repo.create_definition(
        org_id=context.org_id,
        workflow_key=request.workflow_key,
        name=request.name,
        description=request.description,
        definition_json=request.definition_json,
    )
    return {"request_id": context.request_id, "definition": WorkflowDefinitionOut(**row), "verification_status": "created"}


@router.patch("/{definition_id}/activate")
def activate_definition(
    definition_id: str,
    context=Depends(require_workflow_permission("workflow.manage", mode="write")),
) -> dict:
    row = workflow_repo.set_definition_active(context.org_id, definition_id, is_active=True)
    if not row:
        raise HTTPException(status_code=404, detail="Definition not found")
    return {"request_id": context.request_id, "definition": row, "verification_status": "activated"}


@router.patch("/{definition_id}/deactivate")
def deactivate_definition(
    definition_id: str,
    context=Depends(require_workflow_permission("workflow.manage", mode="write")),
) -> dict:
    row = workflow_repo.set_definition_active(context.org_id, definition_id, is_active=False)
    if not row:
        raise HTTPException(status_code=404, detail="Definition not found")
    return {"request_id": context.request_id, "definition": row, "verification_status": "deactivated"}
