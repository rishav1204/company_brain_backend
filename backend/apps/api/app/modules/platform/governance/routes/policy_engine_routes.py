from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.modules.platform.governance.api.deps import require_auditor_read, require_governance_admin, require_governance_write
from app.modules.platform.governance.engine.policy_engine import evaluate
from app.modules.platform.governance.repositories.approval_matrix_repository import approval_matrix_repository
from app.modules.platform.governance.repositories.policy_decision_repository import policy_decision_repository
from app.modules.platform.governance.repositories.policy_exception_repository import policy_exception_repository
from app.modules.platform.governance.services.policy_service import governance_policy_service

router = APIRouter(tags=["governance-policy-engine"])


class PolicyEvaluateRequest(BaseModel):
    action: str
    attrs: dict = Field(default_factory=dict)
    created_by: str | None = None
    object_type: str | None = None
    object_id: str | None = None
    human_approved: bool = False
    actor_type: str | None = None
    dry_run: bool = False


@router.post("/policies/evaluate")
def evaluate_policy(request: PolicyEvaluateRequest, context=Depends(require_governance_write)) -> dict:
    result = evaluate(
        context.org_id,
        action=request.action,
        attrs=request.attrs,
        roles=context.roles,
        actor_user_id=context.user_id,
        created_by=request.created_by,
        object_type=request.object_type,
        object_id=request.object_id,
        human_approved=request.human_approved,
        actor_type=request.actor_type,
        dry_run=request.dry_run,
    )
    return {
        "request_id": context.request_id,
        "allowed": result.allowed,
        "decision": result.decision,
        "reason": result.reason,
        "violations": result.violations,
        "risk_level": result.risk_level,
        "approval_chain": result.approval_chain,
        "decision_id": result.decision_id,
    }


@router.get("/policies/decisions")
def list_decisions(
    context=Depends(require_auditor_read),
    action: str | None = Query(default=None),
    object_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    items = policy_decision_repository.list_decisions(
        context.org_id, action=action, object_type=object_type, limit=limit, offset=offset
    )
    return {"request_id": context.request_id, "items": items, "count": len(items)}


@router.get("/policies/approval-matrix")
def list_approval_matrix(context=Depends(require_auditor_read), action_code: str | None = Query(default=None)) -> dict:
    items = approval_matrix_repository.list_active(context.org_id, action_code=action_code)
    return {"request_id": context.request_id, "items": items}


class MatrixUpsertRequest(BaseModel):
    action_code: str
    approver_role: str
    level: int = 1
    min_amount: float = 0
    max_amount: float | None = None
    department: str | None = None


@router.post("/policies/approval-matrix")
def upsert_matrix(request: MatrixUpsertRequest, context=Depends(require_governance_admin)) -> dict:
    from app.modules.platform.governance.engine import policy_cache_engine

    row = approval_matrix_repository.upsert(context.org_id, **request.model_dump())
    policy_cache_engine.invalidate_org(context.org_id)
    return {"request_id": context.request_id, "row": row}


@router.get("/policies/sod")
def sod_catalog(context=Depends(require_auditor_read)) -> dict:
    from app.modules.core.iam.services.maker_checker_service import MAKER_CHECKER_ACTIONS

    return {"request_id": context.request_id, "maker_checker_actions": sorted(MAKER_CHECKER_ACTIONS)}


class ExceptionRequest(BaseModel):
    policy_code: str
    action: str
    reason: str
    object_type: str | None = None
    object_id: str | None = None


@router.post("/policies/exceptions")
def create_exception(request: ExceptionRequest, context=Depends(require_governance_admin)) -> dict:
    row = policy_exception_repository.create(context.org_id, **request.model_dump())
    return {"request_id": context.request_id, "exception": row}


@router.get("/policies/exceptions")
def list_exceptions(context=Depends(require_auditor_read)) -> dict:
    items = policy_exception_repository.list_open(context.org_id)
    return {"request_id": context.request_id, "items": items}
