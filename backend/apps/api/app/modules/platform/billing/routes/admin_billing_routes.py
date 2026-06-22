from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import build_request_context
from app.core.request_context import RequestContext
from app.modules.platform.billing.services.subscription_service import subscription_service
from app.modules.platform.billing.services.entitlement_service import entitlement_service
from app.modules.platform.billing.services.credit_service import credit_service
from app.modules.platform.billing.services.plan_service import plan_service

router = APIRouter(tags=["admin-billing"])


def _require_tenant_admin(context: RequestContext) -> None:
    if "tenant_admin" not in {r.lower() for r in (context.roles or [])}:
        raise HTTPException(status_code=403, detail="tenant_admin required")


class AssignPlanRequest(BaseModel):
    org_id: str
    plan_key: str = Field(..., min_length=1)


class GrantCreditsRequest(BaseModel):
    org_id: str
    amount: float = Field(..., gt=0)
    reason: str = "admin_grant"


class EntitlementOverrideRequest(BaseModel):
    org_id: str
    feature_code: str
    enabled: bool = True


@router.get("/admin/billing/plans")
def admin_list_plans(context: RequestContext = Depends(build_request_context)) -> dict:
    _require_tenant_admin(context)
    return {"request_id": context.request_id, "plans": plan_service.list_plans()}


@router.post("/admin/billing/subscriptions/assign")
def admin_assign_plan(body: AssignPlanRequest, context: RequestContext = Depends(build_request_context)) -> dict:
    _require_tenant_admin(context)
    sub = subscription_service.assign_plan(body.org_id, body.plan_key)
    return {"request_id": context.request_id, "subscription": sub, "verification_status": "billing_plan_assigned"}


@router.post("/admin/billing/credits/grant")
def admin_grant_credits(body: GrantCreditsRequest, context: RequestContext = Depends(build_request_context)) -> dict:
    _require_tenant_admin(context)
    tx = credit_service.grant_credits(body.org_id, body.amount, reason=body.reason)
    return {"request_id": context.request_id, "transaction": tx, "verification_status": "billing_credits_granted"}


@router.post("/admin/billing/entitlements/override")
def admin_entitlement_override(
    body: EntitlementOverrideRequest,
    context: RequestContext = Depends(build_request_context),
) -> dict:
    _require_tenant_admin(context)
    row = entitlement_service.set_override(body.org_id, body.feature_code, enabled=body.enabled)
    return {"request_id": context.request_id, "entitlement": row, "verification_status": "billing_entitlement_override"}
