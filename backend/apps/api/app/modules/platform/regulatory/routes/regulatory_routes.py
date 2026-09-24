"""Platform operator APIs for India regulatory configuration."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.modules.core.iam.middleware.permission_guard import require_permission
from app.modules.platform.regulatory.services.regulatory_config_service import (
    regulatory_config_service,
)
from app.modules.platform.regulatory.services.regulatory_resolver import (
    RegulatoryConfigError,
)

router = APIRouter(tags=["platform-regulatory"])
_PLATFORM_ADMIN = require_permission("platform.admin")


def _uuid(value: str, label: str = "id") -> str:
    try:
        return str(UUID(str(value).strip()))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {label}") from exc


class ParamBody(BaseModel):
    id: str | None = None
    country_code: str = "IN"
    domain: str = "general"
    param_key: str
    org_id: str | None = None
    value_numeric: float | None = None
    value_text: str | None = None
    value_json: dict[str, Any] | list[Any] | None = None
    unit: str | None = None
    description: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    status: str = "active"


class ThresholdBody(BaseModel):
    id: str | None = None
    country_code: str = "IN"
    threshold_code: str
    org_id: str | None = None
    amount: float
    currency: str = "INR"
    description: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PenaltyBody(BaseModel):
    id: str | None = None
    country_code: str = "IN"
    formula_code: str
    compliance_code_pattern: str = "*"
    org_id: str | None = None
    daily_fee: float = 0
    nil_daily_fee: float | None = None
    fee_cap: float | None = None
    interest_annual_pct: float | None = None
    interest_monthly_pct: float | None = None
    cap_by_turnover_json: list[Any] = Field(default_factory=list)
    effective_from: str | None = None
    effective_to: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SlabSetBody(BaseModel):
    id: str | None = None
    country_code: str = "IN"
    set_code: str
    name: str | None = None
    domain: str = "income_tax"
    org_id: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    status: str = "active"
    bands: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TdsTemplateBody(BaseModel):
    id: str | None = None
    country_code: str = "IN"
    section_code: str
    section_name: str | None = None
    description: str | None = None
    rate_pan: float = 0
    rate_no_pan: float = 20
    threshold_amount: float = 0
    payment_type: str | None = None
    effective_from: str | None = None
    status: str = "active"


@router.get("/ops/platform/regulatory/params")
def list_params(
    domain: str | None = None,
    org_id: str | None = None,
    context=Depends(_PLATFORM_ADMIN),
) -> dict:
    items = regulatory_config_service.list_params(domain=domain, org_id=org_id)
    return {"request_id": context.request_id, "items": items, "verification_status": "regulatory_params"}


@router.put("/ops/platform/regulatory/params")
def put_param(body: ParamBody, context=Depends(_PLATFORM_ADMIN)) -> dict:
    if body.org_id:
        body.org_id = _uuid(body.org_id, "org_id")
    row = regulatory_config_service.upsert_param(body.model_dump(exclude_none=True), actor_id=context.user_id)
    return {"request_id": context.request_id, "param": row, "verification_status": "regulatory_param_upserted"}


@router.get("/ops/platform/regulatory/thresholds")
def list_thresholds(org_id: str | None = None, context=Depends(_PLATFORM_ADMIN)) -> dict:
    items = regulatory_config_service.list_thresholds(org_id=org_id)
    return {"request_id": context.request_id, "items": items, "verification_status": "regulatory_thresholds"}


@router.put("/ops/platform/regulatory/thresholds")
def put_threshold(body: ThresholdBody, context=Depends(_PLATFORM_ADMIN)) -> dict:
    payload = body.model_dump(exclude_none=True)
    if payload.get("org_id"):
        payload["org_id"] = _uuid(payload["org_id"], "org_id")
    row = regulatory_config_service.upsert_threshold(payload, actor_id=context.user_id)
    return {"request_id": context.request_id, "threshold": row, "verification_status": "threshold_upserted"}


@router.get("/ops/platform/regulatory/penalties")
def list_penalties(org_id: str | None = None, context=Depends(_PLATFORM_ADMIN)) -> dict:
    items = regulatory_config_service.list_penalties(org_id=org_id)
    return {"request_id": context.request_id, "items": items, "verification_status": "regulatory_penalties"}


@router.put("/ops/platform/regulatory/penalties")
def put_penalty(body: PenaltyBody, context=Depends(_PLATFORM_ADMIN)) -> dict:
    payload = body.model_dump(exclude_none=True)
    if payload.get("org_id"):
        payload["org_id"] = _uuid(payload["org_id"], "org_id")
    row = regulatory_config_service.upsert_penalty(payload, actor_id=context.user_id)
    return {"request_id": context.request_id, "penalty": row, "verification_status": "penalty_upserted"}


@router.get("/ops/platform/regulatory/slabs")
def list_slabs(context=Depends(_PLATFORM_ADMIN)) -> dict:
    items = regulatory_config_service.list_slab_sets()
    return {"request_id": context.request_id, "items": items, "verification_status": "regulatory_slabs"}


@router.put("/ops/platform/regulatory/slabs")
def put_slab_set(body: SlabSetBody, context=Depends(_PLATFORM_ADMIN)) -> dict:
    payload = body.model_dump(exclude_none=True)
    if payload.get("org_id"):
        payload["org_id"] = _uuid(payload["org_id"], "org_id")
    row = regulatory_config_service.upsert_slab_set(payload, actor_id=context.user_id)
    return {"request_id": context.request_id, "slab_set": row, "verification_status": "slab_upserted"}


@router.get("/ops/platform/regulatory/tds-templates")
def list_tds_templates(context=Depends(_PLATFORM_ADMIN)) -> dict:
    return {
        "request_id": context.request_id,
        "items": regulatory_config_service.list_tds_templates(),
        "verification_status": "tds_templates",
    }


@router.put("/ops/platform/regulatory/tds-templates")
def put_tds_template(body: TdsTemplateBody, context=Depends(_PLATFORM_ADMIN)) -> dict:
    row = regulatory_config_service.upsert_tds_template(body.model_dump(exclude_none=True), actor_id=context.user_id)
    return {"request_id": context.request_id, "template": row, "verification_status": "tds_template_upserted"}


@router.post("/ops/platform/regulatory/tds-templates/apply")
def apply_tds_templates(org_id: str = Query(...), context=Depends(_PLATFORM_ADMIN)) -> dict:
    org_id = _uuid(org_id, "org_id")
    result = regulatory_config_service.apply_tds_templates(org_id, actor_id=context.user_id)
    return {"request_id": context.request_id, **result, "verification_status": "tds_templates_applied"}


@router.get("/ops/platform/regulatory/compliance-templates")
def list_compliance_templates(context=Depends(_PLATFORM_ADMIN)) -> dict:
    return {
        "request_id": context.request_id,
        "items": regulatory_config_service.list_compliance_templates(),
        "verification_status": "compliance_templates",
    }


@router.get("/ops/platform/regulatory/resolve")
def resolve_preview(
    org_id: str | None = None,
    as_of: str | None = None,
    context=Depends(_PLATFORM_ADMIN),
) -> dict:
    if org_id:
        org_id = _uuid(org_id, "org_id")
    try:
        if as_of:
            date.fromisoformat(as_of[:10])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid as_of date") from exc
    try:
        bundle = regulatory_config_service.preview(org_id, as_of)
    except RegulatoryConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, **bundle, "verification_status": "regulatory_resolve"}


@router.get("/ops/platform/orgs/{org_id}/regulatory/params")
def list_org_params(org_id: str, context=Depends(_PLATFORM_ADMIN)) -> dict:
    org_id = _uuid(org_id, "org_id")
    items = regulatory_config_service.list_params(org_id=org_id, include_global=True)
    return {"request_id": context.request_id, "items": items, "verification_status": "org_regulatory_params"}
