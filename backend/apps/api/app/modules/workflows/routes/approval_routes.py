from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.workflows.middleware.workflow_permission_guard import require_workflow_permission
from app.modules.workflows.repositories import approval_repo
from app.modules.workflows.schemas.approval_schema import ApprovalDecideRequest, ApprovalListOut, ApprovalOut
from app.modules.workflows.services.approval_service import approval_service
from app.modules.workflows.services.workflow_service import workflow_service
from app.modules.workflows.validators.approval_validator import validate_decision
from app.services.idempotency import idempotency_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=ApprovalListOut)
def list_pending_approvals(
    context=Depends(require_workflow_permission("approval.read")),
    workflow_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ApprovalListOut:
    if not workflow_service.schema_ready():
        return ApprovalListOut(
            request_id=context.request_id,
            items=[],
            confidence=0.8,
            verification_status="schema_not_ready",
        )
    rows = approval_repo.list_pending(context.org_id, limit=limit + offset)
    if workflow_type:
        rows = [r for r in rows if r.get("workflow_type") == workflow_type]
    rows = rows[offset : offset + limit]
    items = [
        ApprovalOut(
            id=r["id"],
            workflow_instance_id=r["workflow_instance_id"],
            workflow_step_id=r.get("workflow_step_id"),
            decision="pending",
            level=r.get("level") or 1,
            workflow_type=r.get("workflow_type"),
            owner_user_id=r.get("owner_user_id"),
            created_at=r.get("created_at"),
            metadata=r.get("metadata") or {},
        )
        for r in rows
    ]
    return ApprovalListOut(
        request_id=context.request_id,
        items=items,
        confidence=0.96,
        verification_status="verified",
    )


@router.post("/{approval_id}/decide")
def decide_approval(
    approval_id: str,
    request: ApprovalDecideRequest,
    context=Depends(require_workflow_permission("approval.decide", mode="write", action="approve")),
) -> dict:
    if request.idempotency_key and idempotency_service.is_replay(workflow_id=approval_id, key=request.idempotency_key):
        return {
            "request_id": context.request_id,
            "approval_id": approval_id,
            "accepted": True,
            "idempotent_replay": True,
            "verification_status": "idempotent_replay",
        }
    try:
        decision = validate_decision(request.decision)
        row = approval_service.decide(
            org_id=context.org_id,
            user_id=context.user_id,
            roles=context.roles,
            attrs=context.attrs,
            approval_id=approval_id,
            decision=decision,
            reason=request.reason,
            delegate_to=request.delegate_to,
            trace_id=context.request_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if request.idempotency_key:
        idempotency_service.mark(workflow_id=approval_id, key=request.idempotency_key)
    return {
        "request_id": context.request_id,
        "approval_id": approval_id,
        "decision": row.get("decision"),
        "workflow_status": row.get("workflow_status"),
        "accepted": True,
        "confidence": 0.97,
        "verification_status": "approval_decided",
    }
