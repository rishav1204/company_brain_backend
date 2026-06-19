from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.tax.schemas.tax_schema import Gstr2bImportRequest
from app.modules.erp.tax.security.tax_access import enforce_tax_action
from app.modules.erp.tax.security.tax_guard import require_tax_admin, require_tax_read
from app.modules.erp.tax.services.gst_reconciliation_service import gst_reconciliation_service

router = APIRouter()


@router.post("/reconciliation/import-2b")
def import_2b(request: Gstr2bImportRequest, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="gstr2b", object_id="import")
    item = gst_reconciliation_service.import_2b(context.org_id, return_period=request.return_period, rows=request.rows)
    return {"request_id": context.request_id, "item": item}


@router.post("/reconciliation/run")
def run_reconciliation(context=Depends(require_tax_admin), return_period: str = Query(...)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="gst_reconciliation", object_id="run")
    items = gst_reconciliation_service.run_reconciliation(context.org_id, return_period=return_period)
    return {"request_id": context.request_id, "items": items}


@router.get("/reconciliation")
def list_reconciliation(
    context=Depends(require_tax_read),
    return_period: str | None = Query(default=None),
    match_status: str | None = Query(default=None),
) -> dict:
    items = gst_reconciliation_service.list_reconciliations(
        context.org_id, return_period=return_period, match_status=match_status,
    )
    return {"request_id": context.request_id, "items": items}


@router.post("/reconciliation/{reconciliation_id}/resolve")
def resolve_reconciliation(reconciliation_id: str, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="gst_reconciliation", object_id=reconciliation_id, human_approved=True)
    try:
        item = gst_reconciliation_service.resolve(context.org_id, reconciliation_id=reconciliation_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
