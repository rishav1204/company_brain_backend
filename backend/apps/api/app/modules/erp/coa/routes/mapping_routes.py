from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.coa.schemas.account_schema import FinancialMappingCreateRequest, GstMappingCreateRequest
from app.modules.erp.coa.security.coa_guard import require_finance_admin
from app.modules.erp.coa.services.mapping_service import mapping_service

router = APIRouter()


@router.post("/financial-mappings")
def create_financial_mapping(request: FinancialMappingCreateRequest, context=Depends(require_finance_admin)) -> dict:
    item = mapping_service.create_financial_mapping(
        context.org_id,
        account_id=request.account_id,
        statement_type=request.statement_type,
        reporting_category=request.reporting_category,
        company_id=request.company_id,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/financial-mappings")
def list_financial_mappings(context=Depends(build_request_context), company_id: str | None = Query(default=None)) -> dict:
    items = mapping_service.list_financial_mappings(context.org_id, company_id=company_id)
    return {"request_id": context.request_id, "items": items}


@router.delete("/financial-mappings/{mapping_id}")
def delete_financial_mapping(mapping_id: str, context=Depends(require_finance_admin)) -> dict:
    item = mapping_service.delete_financial_mapping(context.org_id, mapping_id=mapping_id)
    return {"request_id": context.request_id, "item": item}


@router.post("/gst-mappings")
def create_gst_mapping(request: GstMappingCreateRequest, context=Depends(require_finance_admin)) -> dict:
    item = mapping_service.create_gst_mapping(
        context.org_id,
        account_id=request.account_id,
        gst_type=request.gst_type,
        itc_eligible=request.itc_eligible,
        company_id=request.company_id,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/gst-mappings")
def list_gst_mappings(context=Depends(build_request_context), company_id: str | None = Query(default=None)) -> dict:
    items = mapping_service.list_gst_mappings(context.org_id, company_id=company_id)
    return {"request_id": context.request_id, "items": items}


@router.delete("/gst-mappings/{mapping_id}")
def delete_gst_mapping(mapping_id: str, context=Depends(require_finance_admin)) -> dict:
    item = mapping_service.delete_gst_mapping(context.org_id, mapping_id=mapping_id)
    return {"request_id": context.request_id, "item": item}

