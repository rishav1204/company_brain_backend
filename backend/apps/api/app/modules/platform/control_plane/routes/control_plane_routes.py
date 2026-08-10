from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import build_request_context
from app.modules.core.iam.middleware.permission_guard import require_permission
from app.modules.platform.control_plane.repositories.control_plane_repository import (
    control_plane_repository,
)
from app.modules.platform.control_plane.services.access_config_service import access_config_service
from app.modules.platform.control_plane.services.activity_service import activity_service
from app.modules.platform.control_plane.services.recycle_service import recycle_service
from app.modules.platform.control_plane.services.support_service import support_service

router = APIRouter(tags=["platform-control-plane"])

_PLATFORM_ADMIN = require_permission("platform.admin")


def _require_uuid(value: str, *, label: str = "id") -> str:
    try:
        return str(UUID(str(value).strip()))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {label}: expected UUID, got {value!r}",
        ) from exc


class OrgControlsPatch(BaseModel):
    lifecycle_status: str | None = None
    login_allowed: bool | None = None
    ai_enabled: bool | None = None
    erp_modules_enabled: bool | None = None
    api_access_allowed: bool | None = None
    support_priority: str | None = None
    notes: str | None = None
    denied_screen_keys: list[str] | None = None


class OrgFeatureToggle(BaseModel):
    enabled: bool
    break_glass: bool = False


class OrgScreensDeny(BaseModel):
    denied_screen_keys: list[str] = Field(default_factory=list)


class UserControlsPut(BaseModel):
    org_id: str
    denied_feature_codes: list[str] = Field(default_factory=list)
    denied_screen_keys: list[str] = Field(default_factory=list)
    force_read_only: bool = False
    reason: str | None = None
    source: str = "platform_owner"
    expires_at: str | None = None


class FeatureUpsert(BaseModel):
    feature_code: str
    name: str | None = None
    description: str | None = None
    category: str = "erp"
    is_ai: bool = False
    status: str = "active"


class ScreenUpsert(BaseModel):
    screen_key: str
    route_path: str
    label: str | None = None
    nav_category: str | None = None
    feature_code: str | None = None
    permission_key: str | None = None
    console: str = "erp"
    sort_order: int = 0


class TicketCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    category: str = "other"
    priority: str = "normal"


class MessageCreate(BaseModel):
    body: str = Field(..., min_length=1)


class TicketStatusPatch(BaseModel):
    status: str
    assigned_to_user_id: str | None = None


class RecycleCapture(BaseModel):
    org_id: str
    entity_type: str
    entity_id: str
    snapshot: dict
    delete_reason: str | None = None


# --- Boot / catalog (tenant + platform) ---


@router.get("/me/boot")
def me_boot(context=Depends(build_request_context)) -> dict:
    if not context.org_id or not context.user_id:
        raise HTTPException(status_code=400, detail="org_id and user_id required")
    boot = access_config_service.effective_boot(
        context.org_id,
        context.user_id,
        permissions=list(context.permissions or []),
    )
    return {"request_id": context.request_id, **boot, "verification_status": "access_boot"}


@router.get("/ops/platform/features")
def list_features(context=Depends(_PLATFORM_ADMIN)) -> dict:
    return {
        "request_id": context.request_id,
        "items": access_config_service.list_feature_catalog(),
        "verification_status": "features_listed",
    }


@router.put("/ops/platform/features/{feature_code}")
def upsert_feature(feature_code: str, body: FeatureUpsert, context=Depends(_PLATFORM_ADMIN)) -> dict:
    payload = body.model_dump()
    payload["feature_code"] = feature_code
    row = control_plane_repository.upsert_feature(payload)
    return {"request_id": context.request_id, "feature": row, "verification_status": "feature_upserted"}


@router.get("/ops/platform/screens")
def list_screens(context=Depends(_PLATFORM_ADMIN)) -> dict:
    return {
        "request_id": context.request_id,
        "items": control_plane_repository.list_screens(),
        "verification_status": "screens_listed",
    }


@router.put("/ops/platform/screens/{screen_key}")
def upsert_screen(screen_key: str, body: ScreenUpsert, context=Depends(_PLATFORM_ADMIN)) -> dict:
    payload = body.model_dump()
    payload["screen_key"] = screen_key
    row = control_plane_repository.upsert_screen(payload)
    return {"request_id": context.request_id, "screen": row, "verification_status": "screen_upserted"}


@router.get("/ops/platform/orgs/{org_id}/controls")
def get_org_controls(org_id: str, context=Depends(_PLATFORM_ADMIN)) -> dict:
    org_id = _require_uuid(org_id, label="org_id")
    return {
        "request_id": context.request_id,
        "controls": access_config_service.get_org_controls(org_id),
        "verification_status": "org_controls",
    }


@router.get("/ops/platform/orgs/{org_id}/access-matrix")
def get_org_access_matrix(org_id: str, context=Depends(_PLATFORM_ADMIN)) -> dict:
    org_id = _require_uuid(org_id, label="org_id")
    matrix = access_config_service.access_matrix(org_id)
    return {
        "request_id": context.request_id,
        **matrix,
        "verification_status": "org_access_matrix",
    }


@router.put("/ops/platform/orgs/{org_id}/features/{feature_code}")
def put_org_feature(
    org_id: str, feature_code: str, body: OrgFeatureToggle, context=Depends(_PLATFORM_ADMIN)
) -> dict:
    org_id = _require_uuid(org_id, label="org_id")
    try:
        row = access_config_service.set_org_feature(
            org_id,
            feature_code,
            enabled=body.enabled,
            break_glass=body.break_glass,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    activity_service.record(
        org_id=org_id,
        actor_user_id=context.user_id,
        actor_type="platform_operator",
        action="config_change",
        entity_type="billing.org_entitlements",
        entity_id=feature_code,
        summary=f"Set feature {feature_code} enabled={body.enabled}",
        metadata=body.model_dump(),
    )
    return {
        "request_id": context.request_id,
        "feature": row,
        "verification_status": "org_feature_updated",
    }


@router.put("/ops/platform/orgs/{org_id}/screens/denied")
def put_org_denied_screens(
    org_id: str, body: OrgScreensDeny, context=Depends(_PLATFORM_ADMIN)
) -> dict:
    org_id = _require_uuid(org_id, label="org_id")
    controls = access_config_service.set_org_denied_screens(
        org_id, body.denied_screen_keys, actor_id=context.user_id
    )
    activity_service.record(
        org_id=org_id,
        actor_user_id=context.user_id,
        actor_type="platform_operator",
        action="config_change",
        entity_type="platform.org_controls.screens",
        entity_id=org_id,
        summary="Updated org denied screens",
        metadata={"denied_screen_keys": body.denied_screen_keys},
    )
    return {
        "request_id": context.request_id,
        "controls": controls,
        "verification_status": "org_screens_denied_updated",
    }


@router.patch("/ops/platform/orgs/{org_id}/controls")
def patch_org_controls(org_id: str, body: OrgControlsPatch, context=Depends(_PLATFORM_ADMIN)) -> dict:
    org_id = _require_uuid(org_id, label="org_id")
    row = access_config_service.patch_org_controls(
        org_id, body.model_dump(exclude_unset=True), actor_id=context.user_id
    )
    activity_service.record(
        org_id=org_id,
        actor_user_id=context.user_id,
        actor_type="platform_operator",
        action="config_change",
        entity_type="platform.org_controls",
        entity_id=org_id,
        summary="Updated org controls",
        metadata=body.model_dump(exclude_unset=True),
    )
    return {"request_id": context.request_id, "controls": row, "verification_status": "org_controls_updated"}


@router.get("/ops/platform/users/{user_id}/controls")
def get_user_controls(
    user_id: str,
    org_id: str = Query(..., description="Tenant org of the user"),
    context=Depends(_PLATFORM_ADMIN),
) -> dict:
    user_id = _require_uuid(user_id, label="user_id")
    org_id = _require_uuid(org_id, label="org_id")
    row = control_plane_repository.get_user_controls(org_id, user_id) or {
        "org_id": org_id,
        "user_id": user_id,
        "denied_feature_codes": [],
        "denied_screen_keys": [],
        "force_read_only": False,
        "reason": None,
        "source": None,
        "expires_at": None,
    }
    return {
        "request_id": context.request_id,
        "controls": row,
        "verification_status": "user_controls",
    }


@router.put("/ops/platform/users/{user_id}/controls")
def put_user_controls(user_id: str, body: UserControlsPut, context=Depends(_PLATFORM_ADMIN)) -> dict:
    user_id = _require_uuid(user_id, label="user_id")
    org_id = _require_uuid(body.org_id, label="org_id")
    payload = body.model_dump(exclude={"org_id"})
    # Normalize lists to plain str for JSON/array storage
    payload["denied_feature_codes"] = [
        str(c).strip() for c in (payload.get("denied_feature_codes") or []) if str(c).strip()
    ]
    payload["denied_screen_keys"] = [
        str(c).strip() for c in (payload.get("denied_screen_keys") or []) if str(c).strip()
    ]
    row = access_config_service.patch_user_controls(
        org_id,
        user_id,
        payload,
        actor_id=context.user_id,
    )
    activity_service.record(
        org_id=org_id,
        actor_user_id=context.user_id,
        actor_type="platform_operator",
        action="config_change",
        entity_type="platform.user_controls",
        entity_id=user_id,
        summary="Updated user controls",
        metadata={**payload, "org_id": org_id},
    )
    return {"request_id": context.request_id, "controls": row, "verification_status": "user_controls_updated"}


# --- Support ---


@router.post("/support/tickets")
def create_support_ticket(body: TicketCreate, context=Depends(build_request_context)) -> dict:
    if not context.org_id or not context.user_id:
        raise HTTPException(status_code=400, detail="auth required")
    ticket = support_service.create_ticket(
        context.org_id,
        user_id=context.user_id,
        subject=body.subject,
        body=body.body,
        category=body.category,
        priority=body.priority,
    )
    return {"request_id": context.request_id, "ticket": ticket, "verification_status": "support_ticket_created"}


@router.get("/support/tickets")
def list_my_tickets(
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    context=Depends(build_request_context),
) -> dict:
    items = support_service.list_for_org(context.org_id, status=status, limit=limit)
    return {"request_id": context.request_id, "items": items, "count": len(items)}


@router.get("/support/tickets/{ticket_id}")
def get_ticket_thread(ticket_id: str, context=Depends(build_request_context)) -> dict:
    thread = support_service.get_thread(ticket_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if str(thread["ticket"]["org_id"]) != str(context.org_id):
        raise HTTPException(status_code=403, detail="Not your org ticket")
    return {"request_id": context.request_id, **thread}


@router.post("/support/tickets/{ticket_id}/messages")
def reply_ticket(ticket_id: str, body: MessageCreate, context=Depends(build_request_context)) -> dict:
    ticket = control_plane_repository.get_ticket(ticket_id)
    if not ticket or str(ticket["org_id"]) != str(context.org_id):
        raise HTTPException(status_code=404, detail="Ticket not found")
    msg = support_service.reply(
        ticket_id,
        org_id=context.org_id,
        user_id=context.user_id,
        body=body.body,
        author_side="customer",
    )
    return {"request_id": context.request_id, "message": msg}


@router.get("/ops/platform/support/tickets")
def platform_list_tickets(
    org_id: str | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    context=Depends(_PLATFORM_ADMIN),
) -> dict:
    items = support_service.list_all(org_id=org_id, status=status, limit=limit)
    return {"request_id": context.request_id, "items": items, "count": len(items)}


@router.get("/ops/platform/support/tickets/{ticket_id}")
def platform_get_ticket(ticket_id: str, context=Depends(_PLATFORM_ADMIN)) -> dict:
    thread = support_service.get_thread(ticket_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"request_id": context.request_id, **thread}


@router.post("/ops/platform/support/tickets/{ticket_id}/messages")
def platform_reply_ticket(ticket_id: str, body: MessageCreate, context=Depends(_PLATFORM_ADMIN)) -> dict:
    ticket = control_plane_repository.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    msg = support_service.reply(
        ticket_id,
        org_id=ticket["org_id"],
        user_id=context.user_id,
        body=body.body,
        author_side="platform",
    )
    return {"request_id": context.request_id, "message": msg}


@router.patch("/ops/platform/support/tickets/{ticket_id}")
def platform_patch_ticket(ticket_id: str, body: TicketStatusPatch, context=Depends(_PLATFORM_ADMIN)) -> dict:
    row = control_plane_repository.update_ticket_status(
        ticket_id, status=body.status, assigned_to=body.assigned_to_user_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return {"request_id": context.request_id, "ticket": row}


# --- Activity ---


@router.get("/activity")
def tenant_activity(
    action: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    context=Depends(build_request_context),
) -> dict:
    items = activity_service.list_for_org(context.org_id, action=action, limit=limit)
    return {"request_id": context.request_id, "items": items, "count": len(items)}


@router.get("/ops/platform/activity")
def platform_activity(
    org_id: str | None = None,
    action: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    context=Depends(_PLATFORM_ADMIN),
) -> dict:
    items = activity_service.list_all(org_id=org_id, action=action, limit=limit)
    return {"request_id": context.request_id, "items": items, "count": len(items)}


# --- Recycle bin ---


@router.get("/recycle-bin")
def tenant_recycle(limit: int = Query(50, ge=1, le=200), context=Depends(build_request_context)) -> dict:
    items = recycle_service.list_items(org_id=context.org_id, limit=limit)
    return {"request_id": context.request_id, "items": items, "count": len(items)}


@router.post("/recycle-bin/{recycle_id}/restore")
def tenant_restore(recycle_id: str, context=Depends(build_request_context)) -> dict:
    entry = control_plane_repository.get_recycle(recycle_id)
    if not entry or str(entry.get("org_id")) != str(context.org_id):
        raise HTTPException(status_code=404, detail="Not found")
    try:
        result = recycle_service.restore(recycle_id, restored_by=context.user_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": result, "verification_status": "recycle_restored"}


@router.get("/ops/platform/recycle-bin")
def platform_recycle(
    org_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    context=Depends(_PLATFORM_ADMIN),
) -> dict:
    items = recycle_service.list_items(org_id=org_id, limit=limit)
    return {"request_id": context.request_id, "items": items, "count": len(items)}


@router.post("/ops/platform/recycle-bin/{recycle_id}/restore")
def platform_restore(recycle_id: str, context=Depends(_PLATFORM_ADMIN)) -> dict:
    try:
        result = recycle_service.restore(recycle_id, restored_by=context.user_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": result, "verification_status": "recycle_restored"}


@router.post("/ops/platform/recycle-bin/capture")
def platform_capture(body: RecycleCapture, context=Depends(_PLATFORM_ADMIN)) -> dict:
    entry = recycle_service.capture(
        org_id=body.org_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        snapshot=body.snapshot,
        deleted_by=context.user_id,
        delete_reason=body.delete_reason,
        source="platform",
    )
    return {"request_id": context.request_id, "item": entry, "verification_status": "recycle_captured"}
