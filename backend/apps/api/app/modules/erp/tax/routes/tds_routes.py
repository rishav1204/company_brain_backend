from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.ports.intelligence_registry import intelligence_registry
from app.modules.erp.tax.schemas.tax_schema import (
    Form16aGenerateRequest,
    Tds26asReconcileRequest,
    TdsCalculateRequest,
    TdsChallanCreateRequest,
    TdsChallanPayRequest,
    TdsChallanValidateRequest,
    TdsDeductRequest,
    TdsRecommendSectionRequest,
    TdsReturnGenerateRequest,
    TdsReturnReviewRequest,
    TdsReviewRequest,
)
from app.modules.erp.tax.security.tax_access import enforce_tax_action
from app.modules.erp.tax.security.tax_guard import require_tax_admin, require_tax_read
from app.modules.erp.tax.services.form16a_service import form16a_service
from app.modules.erp.tax.services.tds_challan_service import tds_challan_service
from app.modules.erp.tax.services.tds_reconciliation_service import tds_reconciliation_service
from app.modules.erp.tax.services.tds_return_service import tds_return_service
from app.modules.erp.tax.services.tds_service import tds_service
from app.modules.erp.tax.services.tcs_service import tcs_service

router = APIRouter()


@router.get("/transactions")
def list_tds_transactions(context=Depends(require_tax_read)) -> dict:
    items = tds_service.list_transactions(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/sections")
def list_tds_sections(context=Depends(require_tax_read)) -> dict:
    items = tds_service.list_sections(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/rules")
def list_tds_rules(context=Depends(require_tax_read)) -> dict:
    items = tds_service.list_rules(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/setup/accounts")
def setup_tax_accounts(context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="tds_setup", object_id="accounts")
    from app.modules.erp.tax.services.tax_account_setup_service import tax_account_setup_service

    item = tax_account_setup_service.ensure_tax_accounts(context.org_id, auto_create=True)
    return {"request_id": context.request_id, "item": item}


@router.post("/calculate")
def calculate_tds(request: TdsCalculateRequest, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="tds", object_id="preview", amount=request.gross_amount)
    try:
        item = tds_service.calculate(
            context.org_id,
            section_code=request.section_code,
            gross_amount=request.gross_amount,
            prior_ytd=request.prior_ytd,
            pan_present=request.pan_present,
            vendor_id=request.vendor_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/deduct")
def deduct_tds(request: TdsDeductRequest, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="tds", object_id=request.payment_id)
    try:
        item = tds_service.deduct(context.org_id, payment_id=request.payment_id, section_code=request.section_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/liability")
def tds_liability(
    context=Depends(require_tax_read),
    quarter: str | None = Query(default=None),
    financial_year: str | None = Query(default=None),
) -> dict:
    item = tds_service.liability_summary(context.org_id, quarter=quarter, financial_year=financial_year)
    return {"request_id": context.request_id, "item": item}


@router.get("/vendor-summary")
def tds_vendor_summary(
    context=Depends(require_tax_read),
    vendor_id: str | None = Query(default=None),
) -> dict:
    items = tds_service.vendor_summary(context.org_id, vendor_id=vendor_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/challan")
def create_tds_challan(request: TdsChallanCreateRequest, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="tds_challan", object_id="new", amount=request.amount)
    item = tds_challan_service.create_challan(
        context.org_id,
        amount=request.amount,
        deposit_date=request.deposit_date,
        bsr_code=request.bsr_code,
        cin=request.cin,
        challan_no=request.challan_no,
        quarter=request.quarter,
        financial_year=request.financial_year,
        transaction_ids=request.transaction_ids,
        tax_type=request.tax_type,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/challans")
def list_tds_challans(
    context=Depends(require_tax_read),
    status: str | None = Query(default=None),
) -> dict:
    items = tds_challan_service.list_challans(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.post("/challan/{challan_id}/pay")
def pay_tds_challan(challan_id: str, request: TdsChallanPayRequest, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="tds_challan", object_id=challan_id)
    item = tds_challan_service.mark_paid(
        context.org_id,
        challan_id=challan_id,
        challan_no=request.challan_no,
        bsr_code=request.bsr_code,
        cin=request.cin,
        deposit_date=request.deposit_date,
    )
    return {"request_id": context.request_id, "item": item}


@router.post("/form16a")
def generate_form16a(
    request: Form16aGenerateRequest,
    context=Depends(require_tax_admin),
    regenerate: bool = Query(default=False),
) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="form16a", object_id=request.vendor_id)
    item = form16a_service.generate(
        context.org_id,
        vendor_id=request.vendor_id,
        quarter=request.quarter,
        financial_year=request.financial_year,
        regenerate=regenerate,
        uploaded_by=context.user_id,
    )
    return {"request_id": context.request_id, "item": item}


@router.post("/reconcile/26as")
def reconcile_26as(request: Tds26asReconcileRequest, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="tds_reconciliation", object_id="26as")
    item = tds_reconciliation_service.reconcile_26as(
        context.org_id,
        financial_year=request.financial_year,
        quarter=request.quarter,
        rows=request.rows,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/reconciliations")
def list_tds_reconciliations(context=Depends(require_tax_read)) -> dict:
    items = tds_reconciliation_service.list_reconciliations(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/tcs/transactions")
def list_tcs_transactions(context=Depends(require_tax_read)) -> dict:
    items = tcs_service.list_transactions(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/ai/recommend-section")
def tds_recommend_section(request: TdsRecommendSectionRequest, context=Depends(require_tax_read)) -> dict:
    rules = tds_service.list_rules(context.org_id)
    vendor_meta = {}
    if request.vendor_id:
        from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository

        vendor = vendor_repository.get(context.org_id, vendor_id=request.vendor_id) or {}
        vendor_meta = vendor.get("metadata") if isinstance(vendor.get("metadata"), dict) else {}
    item = intelligence_registry.tax().recommend_section(
        payment_type=request.payment_type,
        expense_category=request.expense_category,
        vendor_metadata=vendor_meta,
        amount=request.amount,
        rules=rules,
    )
    return {"request_id": context.request_id, "item": item}


@router.post("/ai/review")
def tds_review_vendor(request: TdsReviewRequest, context=Depends(require_tax_read)) -> dict:
    from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository

    vendor = vendor_repository.get(context.org_id, vendor_id=request.vendor_id) or {}
    txs = tds_service.list_transactions(context.org_id)
    item = intelligence_registry.tax().review_vendor_quarter(
        vendor_id=request.vendor_id,
        quarter=request.quarter,
        financial_year=request.financial_year,
        transactions=txs,
        vendor_pan=vendor.get("pan"),
        rules=tds_service.list_rules(context.org_id),
    )
    return {"request_id": context.request_id, "item": item}


@router.post("/ai/return-review")
def tds_return_review(request: TdsReturnReviewRequest, context=Depends(require_tax_read)) -> dict:
    row = tds_return_service.get_return(context.org_id, return_id=request.return_id)
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    item = intelligence_registry.tax().review_return_payload(
        payload=payload,
        form_type=str(row.get("form_type") or "26Q"),
    )
    return {"request_id": context.request_id, "item": item}


@router.post("/ai/challan-validate")
def tds_challan_validate(request: TdsChallanValidateRequest, context=Depends(require_tax_read)) -> dict:
    from app.modules.platform.integrations.connectors.tds.tds_connector_resolver import resolve_tds_filing_connector

    connector = resolve_tds_filing_connector()
    if not connector or not hasattr(connector, "validate_challan"):
        raise HTTPException(status_code=503, detail="TDS challan validator not available")
    item = connector.validate_challan(challan_no=request.challan_no, bsr_code=request.bsr_code, amount=request.amount)
    return {"request_id": context.request_id, "item": item}


@router.post("/returns/generate")
def generate_tds_return(request: TdsReturnGenerateRequest, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="tds_return", object_id="new")
    item = tds_return_service.generate_return(
        context.org_id, return_period=request.return_period, form_type=request.form_type
    )
    return {"request_id": context.request_id, "item": item}


@router.post("/return/26q")
def generate_tds_return_26q(request: TdsReturnGenerateRequest, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="tds_return", object_id="new")
    item = tds_return_service.generate_return(
        context.org_id, return_period=request.return_period, form_type="26Q"
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/returns")
def list_tds_returns(context=Depends(require_tax_read)) -> dict:
    items = tds_return_service.list_returns(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/returns/{return_id}")
def get_tds_return(return_id: str, context=Depends(require_tax_read)) -> dict:
    try:
        item = tds_return_service.get_return(context.org_id, return_id=return_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/returns/{return_id}/submit")
def submit_tds_return(return_id: str, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="tds_return", object_id=return_id)
    item = tds_return_service.submit_for_approval(context.org_id, return_id=return_id, started_by=context.user_id)
    return {"request_id": context.request_id, "item": item}


@router.post("/returns/{return_id}/fvu")
def generate_tds_fvu(return_id: str, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="tds_return", object_id=return_id)
    try:
        item = tds_return_service.generate_fvu(context.org_id, return_id=return_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/returns/{return_id}/file")
def file_tds_return(return_id: str, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tds.file", object_type="tds_return", object_id=return_id, human_approved=True)
    try:
        item = tds_return_service.file_return(context.org_id, return_id=return_id, filed_by=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
