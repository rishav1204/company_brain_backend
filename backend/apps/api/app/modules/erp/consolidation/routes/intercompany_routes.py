from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import build_request_context
from app.modules.erp.consolidation.security.consolidation_guard import (
    require_consolidation_read,
    require_intercompany_write,
)
from app.modules.erp.consolidation.services.intercompany_service import intercompany_service

router = APIRouter(tags=["consolidation-intercompany"])


class IntercompanyCreateRequest(BaseModel):
    source_company_id: str
    target_company_id: str
    transaction_type: str
    amount: float = Field(gt=0)
    currency: str = "INR"
    source_document_type: str | None = None
    source_document_id: str | None = None


class IntercompanyMatchRequest(BaseModel):
    matched_transaction_id: str


@router.post("/intercompany")
def create_intercompany(request: IntercompanyCreateRequest, context=Depends(build_request_context)) -> dict:
    require_intercompany_write(context, company_id=request.source_company_id)
    try:
        item = intercompany_service.register(context.org_id, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/intercompany")
def list_intercompany(
    context=Depends(build_request_context),
    source_company_id: str | None = Query(default=None),
    target_company_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict:
    require_consolidation_read(context)
    items = intercompany_service.list_transactions(
        context.org_id,
        source_company_id=source_company_id,
        target_company_id=target_company_id,
        status=status,
    )
    return {"request_id": context.request_id, "items": items}


@router.get("/intercompany/balances")
def list_ic_balances(context=Depends(build_request_context)) -> dict:
    require_consolidation_read(context)
    return {"request_id": context.request_id, "items": intercompany_service.list_balances(context.org_id)}


@router.post("/intercompany/{tx_id}/match")
def match_intercompany(
    tx_id: str,
    request: IntercompanyMatchRequest,
    context=Depends(build_request_context),
) -> dict:
    require_intercompany_write(context)
    item = intercompany_service.match(
        context.org_id, tx_id=tx_id, matched_tx_id=request.matched_transaction_id
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/intercompany/mismatches")
def ic_mismatches(context=Depends(build_request_context)) -> dict:
    require_consolidation_read(context)
    items = intercompany_service.detect_mismatches(context.org_id)
    return {"request_id": context.request_id, "items": items}
