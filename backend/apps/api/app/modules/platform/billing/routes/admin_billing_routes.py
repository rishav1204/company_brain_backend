from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.modules.core.iam.middleware.permission_guard import require_permission
from app.modules.platform.billing.services.subscription_service import subscription_service
from app.modules.platform.billing.services.entitlement_service import entitlement_service
from app.modules.platform.billing.services.credit_service import credit_service
from app.modules.platform.billing.services.plan_service import plan_service

router = APIRouter(tags=["admin-billing"])

_PLATFORM_ADMIN = require_permission("platform.admin")


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
    break_glass: bool = False
    expires_at: str | None = None


class CreatePlanRequest(BaseModel):
    plan_key: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    tier: int = Field(default=1, ge=1)
    monthly_price_inr: float = Field(default=0, ge=0)
    included_ai_credits: float = Field(default=0, ge=0)
    status: str = "active"
    features: list[dict | str] | None = None
    limits: list[dict] | None = None


class UpdatePlanRequest(BaseModel):
    name: str | None = None
    tier: int | None = Field(default=None, ge=1)
    monthly_price_inr: float | None = Field(default=None, ge=0)
    included_ai_credits: float | None = Field(default=None, ge=0)
    status: str | None = None


class ReplaceFeaturesRequest(BaseModel):
    features: list[dict | str] = Field(default_factory=list)


class ReplaceLimitsRequest(BaseModel):
    limits: list[dict] = Field(default_factory=list)


class DisableAiRequest(BaseModel):
    org_id: str


@router.get("/admin/billing/plans")
def admin_list_plans(context=Depends(_PLATFORM_ADMIN)) -> dict:
    return {"request_id": context.request_id, "plans": plan_service.list_plans()}


@router.get("/admin/billing/plans/{plan_key}")
def admin_get_plan(plan_key: str, context=Depends(_PLATFORM_ADMIN)) -> dict:
    plan = plan_service.get_plan(plan_key)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"request_id": context.request_id, "plan": plan, "verification_status": "billing_plan_detail"}


@router.post("/admin/billing/plans")
def admin_create_plan(body: CreatePlanRequest, context=Depends(_PLATFORM_ADMIN)) -> dict:
    try:
        plan = plan_service.create_plan(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "plan": plan, "verification_status": "billing_plan_created"}


@router.patch("/admin/billing/plans/{plan_key}")
def admin_update_plan(plan_key: str, body: UpdatePlanRequest, context=Depends(_PLATFORM_ADMIN)) -> dict:
    try:
        plan = plan_service.update_plan(plan_key, body.model_dump(exclude_unset=True))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "plan": plan, "verification_status": "billing_plan_updated"}


@router.put("/admin/billing/plans/{plan_key}/features")
def admin_replace_plan_features(
    plan_key: str, body: ReplaceFeaturesRequest, context=Depends(_PLATFORM_ADMIN)
) -> dict:
    if not plan_service.get_plan(plan_key) and plan_key not in plan_service.list_plans():
        # ensure plan row exists as soft create of features
        pass
    codes = plan_service.replace_features(plan_key, body.features)
    return {
        "request_id": context.request_id,
        "plan_key": plan_key,
        "features": codes,
        "verification_status": "billing_plan_features_replaced",
    }


@router.put("/admin/billing/plans/{plan_key}/limits")
def admin_replace_plan_limits(
    plan_key: str, body: ReplaceLimitsRequest, context=Depends(_PLATFORM_ADMIN)
) -> dict:
    limits = plan_service.replace_limits(plan_key, body.limits)
    return {
        "request_id": context.request_id,
        "plan_key": plan_key,
        "limits": limits,
        "verification_status": "billing_plan_limits_replaced",
    }


@router.post("/admin/billing/subscriptions/assign")
def admin_assign_plan(body: AssignPlanRequest, context=Depends(_PLATFORM_ADMIN)) -> dict:
    try:
        sub = subscription_service.assign_plan(body.org_id, body.plan_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "subscription": sub, "verification_status": "billing_plan_assigned"}


@router.post("/admin/billing/credits/grant")
def admin_grant_credits(body: GrantCreditsRequest, context=Depends(_PLATFORM_ADMIN)) -> dict:
    tx = credit_service.grant_credits(body.org_id, body.amount, reason=body.reason)
    return {"request_id": context.request_id, "transaction": tx, "verification_status": "billing_credits_granted"}


@router.post("/admin/billing/entitlements/override")
def admin_entitlement_override(
    body: EntitlementOverrideRequest,
    context=Depends(_PLATFORM_ADMIN),
) -> dict:
    try:
        row = entitlement_service.set_override(
            body.org_id,
            body.feature_code,
            enabled=body.enabled,
            expires_at=body.expires_at,
            break_glass=body.break_glass,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "entitlement": row, "verification_status": "billing_entitlement_override"}


@router.post("/admin/billing/orgs/{org_id}/disable-ai")
def admin_disable_ai(org_id: str, context=Depends(_PLATFORM_ADMIN)) -> dict:
    rows = entitlement_service.disable_ai_features(org_id)
    return {
        "request_id": context.request_id,
        "org_id": org_id,
        "overrides": rows,
        "verification_status": "billing_ai_disabled",
    }
