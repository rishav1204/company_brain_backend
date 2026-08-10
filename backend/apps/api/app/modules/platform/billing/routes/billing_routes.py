from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.core.request_context import RequestContext
from app.modules.platform.billing.services.subscription_service import subscription_service
from app.modules.platform.billing.services.entitlement_service import entitlement_service
from app.modules.platform.billing.services.usage_service import usage_service
from app.modules.platform.billing.services.credit_service import credit_service
from app.modules.platform.billing.services.plan_service import plan_service

router = APIRouter(tags=["billing"])


def _require_org(context: RequestContext) -> str:
    if not context.org_id:
        raise HTTPException(status_code=400, detail="org_id required")
    return context.org_id


@router.get("/billing/subscription")
def get_subscription(context: RequestContext = Depends(build_request_context)) -> dict:
    org_id = _require_org(context)
    sub = subscription_service.get_subscription(org_id)
    plan_key = subscription_service.get_plan_key(org_id)
    return {
        "request_id": context.request_id,
        "subscription": sub,
        "plan_key": plan_key,
        "verification_status": "billing_subscription",
    }


@router.get("/billing/entitlements")
def get_entitlements(context: RequestContext = Depends(build_request_context)) -> dict:
    org_id = _require_org(context)
    features = entitlement_service.list_effective_features(org_id)
    return {
        "request_id": context.request_id,
        "plan_key": subscription_service.get_plan_key(org_id),
        "features": features,
        "verification_status": "billing_entitlements",
    }


@router.get("/billing/usage")
def get_usage(context: RequestContext = Depends(build_request_context)) -> dict:
    org_id = _require_org(context)
    return {
        "request_id": context.request_id,
        "usage": usage_service.usage_summary(org_id),
        "verification_status": "billing_usage",
    }


@router.get("/billing/credits")
def get_credits(context: RequestContext = Depends(build_request_context)) -> dict:
    org_id = _require_org(context)
    balance = credit_service.get_balance(org_id)
    return {
        "request_id": context.request_id,
        "balance": balance,
        "verification_status": "billing_credits",
    }


@router.get("/billing/plans")
def list_plans(context: RequestContext = Depends(build_request_context)) -> dict:
    return {
        "request_id": context.request_id,
        "plans": plan_service.list_plans(),
        "verification_status": "billing_plans",
    }
