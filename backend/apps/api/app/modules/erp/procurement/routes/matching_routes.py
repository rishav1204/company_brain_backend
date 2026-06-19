from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.procurement.schemas.procurement_schema import MatchOverrideRequest, MatchRunRequest
from app.modules.erp.procurement.security.procurement_guard import (
    require_procurement_match,
    require_procurement_override,
    require_procurement_read,
)
from app.modules.erp.procurement.services.matching_service import matching_service

router = APIRouter()


@router.get("/matches")
def list_matches(
    context=Depends(require_procurement_read),
    po_id: str | None = Query(default=None),
) -> dict:
    items = matching_service.list_matches(context.org_id, po_id=po_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/match")
def run_match(request: MatchRunRequest, context=Depends(require_procurement_match)) -> dict:
    try:
        item = matching_service.run_match(
            context.org_id,
            po_id=request.po_id,
            grn_id=request.grn_id,
            ap_invoice_id=request.ap_invoice_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/match/{match_id}/override")
def override_match(match_id: str, request: MatchOverrideRequest, context=Depends(require_procurement_override)) -> dict:
    try:
        item = matching_service.apply_override(
            context.org_id,
            match_id=match_id,
            actor_id=context.user_id,
            reason=request.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
