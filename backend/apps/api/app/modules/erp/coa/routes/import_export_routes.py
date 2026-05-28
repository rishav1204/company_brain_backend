from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.erp.coa.schemas.import_schema import CoaImportRequest
from app.modules.erp.coa.security.coa_guard import require_finance_admin
from app.modules.erp.coa.services.import_export_service import import_export_service

router = APIRouter()


@router.get("/coa/template")
def coa_template(context=Depends(build_request_context)) -> dict:
    return {"request_id": context.request_id, "item": import_export_service.template()}


@router.post("/coa/import")
def import_coa(request: CoaImportRequest, context=Depends(require_finance_admin)) -> dict:
    item = import_export_service.import_coa(context.org_id, rows=request.rows)
    return {"request_id": context.request_id, "item": item}

