from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.workflows.middleware.workflow_permission_guard import require_workflow_permission
from app.modules.workflows.repositories import task_repo
from app.modules.workflows.schemas.escalation_schema import TaskAssignRequest, TaskListOut, TaskOut
from app.modules.workflows.services.workflow_service import workflow_service

router = APIRouter(prefix="/tasks", tags=["workflow-tasks"])


@router.get("", response_model=TaskListOut)
def list_tasks(
    context=Depends(require_workflow_permission("task.read")),
    assigned_to: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> TaskListOut:
    assignee = assigned_to or context.user_id
    if not workflow_service.schema_ready():
        return TaskListOut(
            request_id=context.request_id,
            items=[],
            confidence=0.8,
            verification_status="schema_not_ready",
        )
    rows = task_repo.list_tasks(
        context.org_id,
        assigned_to=assignee,
        status=status,
        limit=limit,
        offset=offset,
    )
    items = [
        TaskOut(
            id=r["id"],
            task_type=r["task_type"],
            status=r["status"],
            assigned_to=r.get("assigned_to"),
            due_at=r.get("due_at"),
            workflow_instance_id=r["workflow_instance_id"],
            workflow_type=r.get("workflow_type"),
            payload=r.get("payload") or {},
        )
        for r in rows
    ]
    return TaskListOut(
        request_id=context.request_id,
        items=items,
        confidence=0.95,
        verification_status="verified",
    )


@router.post("/{task_id}/assign")
def assign_task(
    task_id: str,
    request: TaskAssignRequest,
    context=Depends(require_workflow_permission("task.assign", mode="write")),
) -> dict:
    if not workflow_service.schema_ready():
        raise HTTPException(status_code=503, detail="Workflow engine schema not ready")
    row = task_repo.assign_task(context.org_id, task_id, request.assigned_to)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "request_id": context.request_id,
        "task_id": task_id,
        "assigned_to": row.get("assigned_to"),
        "verification_status": "assigned",
    }


@router.post("/{task_id}/complete")
def complete_task(
    task_id: str,
    context=Depends(require_workflow_permission("task.read", mode="write")),
) -> dict:
    if not workflow_service.schema_ready():
        raise HTTPException(status_code=503, detail="Workflow engine schema not ready")
    ok = task_repo.complete_task(context.org_id, task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"request_id": context.request_id, "task_id": task_id, "verification_status": "completed"}
