from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.modules.platform.governance.api.deps import (
    require_auditor_read,
    require_governance_admin,
    require_governance_write,
)
from app.modules.platform.governance.services.policy_service import governance_policy_service

router = APIRouter(tags=["governance-policies"])


class PolicyUpsertRequest(BaseModel):
    policy_key: str
    policy_type: str
    conditions: dict = Field(default_factory=dict)
    actions: dict = Field(default_factory=dict)
    is_active: bool = True
    priority: int = 100


class PolicySimulateRequest(BaseModel):
    action: str
    attrs: dict = Field(default_factory=dict)
    created_by: str | None = None


@router.get("/policies")
def list_policies(context=Depends(require_auditor_read), policy_type: str | None = None) -> dict:
    items = governance_policy_service.list_policies(context.org_id, policy_type=policy_type)
    return {"request_id": context.request_id, "items": items}


@router.post("/policies")
def upsert_policy(request: PolicyUpsertRequest, context=Depends(require_governance_admin)) -> dict:
    row = governance_policy_service.upsert_policy(context.org_id, **request.model_dump())
    return {"request_id": context.request_id, "policy": row}


@router.post("/policies/simulate")
def simulate_policy(request: PolicySimulateRequest, context=Depends(require_governance_write)) -> dict:
    result = governance_policy_service.simulate(
        context.org_id,
        action=request.action,
        attrs=request.attrs,
        roles=context.roles,
        created_by=request.created_by,
        actor_user_id=context.user_id,
    )
    return {
        "request_id": context.request_id,
        "allowed": result.allowed,
        "reason": result.reason,
        "violations": result.violations,
    }
