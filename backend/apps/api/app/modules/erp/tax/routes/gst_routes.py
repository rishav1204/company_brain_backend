from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.tax.schemas.tax_schema import GstCalculateRequest, GstRegistrationCreate, ItcBlockedRuleCreate, ItcBlockedRuleUpdate, TaxRateCreate
from app.modules.erp.tax.security.tax_access import enforce_tax_action
from app.modules.erp.tax.security.tax_guard import require_tax_admin, require_tax_read
from app.modules.erp.tax.services.gst_calculation_service import gst_calculation_service
from app.modules.erp.tax.services.gst_service import gst_service
from app.modules.erp.tax.services.itc_service import itc_service

router = APIRouter()


@router.post("/calculate")
def calculate_gst(request: GstCalculateRequest, context=Depends(require_tax_read)) -> dict:
    try:
        result = gst_calculation_service.calculate(
            context.org_id,
            taxable_value=request.taxable_value,
            gst_rate=request.gst_rate,
            supplier_state=request.supplier_state,
            place_of_supply=request.place_of_supply,
            party_gstin=request.party_gstin,
            gst_type=request.gst_type,
            export_zero_rated=request.export_zero_rated,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "calculation": result}


@router.post("/registrations")
def create_registration(request: GstRegistrationCreate, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="gst_registration", object_id="new")
    try:
        item = gst_service.create_registration(
            context.org_id,
            gstin=request.gstin,
            legal_name=request.legal_name,
            trade_name=request.trade_name,
            state_code=request.state_code,
            registration_type=request.registration_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/registrations")
def list_registrations(context=Depends(require_tax_read)) -> dict:
    items = gst_service.list_registrations(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/transactions")
def list_transactions(
    context=Depends(require_tax_read),
    return_period: str | None = Query(default=None),
    gst_type: str | None = Query(default=None),
) -> dict:
    items = gst_service.list_transactions(context.org_id, return_period=return_period, gst_type=gst_type)
    return {"request_id": context.request_id, "items": items}


@router.get("/itc")
def list_itc(context=Depends(require_tax_read), status: str | None = Query(default=None)) -> dict:
    items = itc_service.list_ledger(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.get("/itc/summary")
def itc_summary(context=Depends(require_tax_read), return_period: str | None = Query(default=None)) -> dict:
    item = itc_service.summary(context.org_id, return_period=return_period)
    return {"request_id": context.request_id, "item": item}


@router.get("/itc/blocked-rules")
def list_blocked_rules(context=Depends(require_tax_read)) -> dict:
    from app.modules.erp.tax.repositories.itc_repository import itc_blocked_rules_repository

    items = itc_blocked_rules_repository.list_all(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/itc/blocked-rules")
def create_blocked_rule(request: ItcBlockedRuleCreate, context=Depends(require_tax_admin)) -> dict:
    from app.modules.erp.tax.repositories.itc_repository import itc_blocked_rules_repository

    enforce_tax_action(context, action="tax.modify", object_type="itc_blocked_rule", object_id="new")
    item = itc_blocked_rules_repository.create(
        context.org_id,
        category=request.category,
        description=request.description,
        block_percentage=request.block_percentage,
    )
    return {"request_id": context.request_id, "item": item}


@router.patch("/itc/blocked-rules/{rule_id}")
def update_blocked_rule(rule_id: str, request: ItcBlockedRuleUpdate, context=Depends(require_tax_admin)) -> dict:
    from app.modules.erp.tax.repositories.itc_repository import itc_blocked_rules_repository

    enforce_tax_action(context, action="tax.modify", object_type="itc_blocked_rule", object_id=rule_id)
    try:
        item = itc_blocked_rules_repository.update(
            context.org_id,
            rule_id=rule_id,
            description=request.description,
            block_percentage=request.block_percentage,
            is_active=request.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/rates")
def list_tax_rates(context=Depends(require_tax_read)) -> dict:
    from app.modules.erp.tax.services.tax_rate_service import tax_rate_service

    items = tax_rate_service.list_rates(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/rates")
def create_tax_rate(request: TaxRateCreate, context=Depends(require_tax_admin)) -> dict:
    from app.modules.erp.tax.services.tax_rate_service import tax_rate_service

    enforce_tax_action(context, action="tax.modify", object_type="tax_rate", object_id="new")
    item = tax_rate_service.create_rate(
        context.org_id,
        hsn_sac=request.hsn_sac,
        description=request.description,
        gst_rate=request.gst_rate,
        cess_rate=request.cess_rate,
    )
    return {"request_id": context.request_id, "item": item}


@router.post("/itc/{itc_id}/claim")
def claim_itc(itc_id: str, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="itc_ledger", object_id=itc_id, human_approved=True)
    from app.modules.erp.tax.repositories.itc_repository import itc_ledger_repository

    rows = itc_ledger_repository.list(context.org_id, limit=500)
    row = next((r for r in rows if str(r.get("id")) == itc_id), None)
    if not row:
        raise HTTPException(status_code=404, detail="ITC entry not found")
    amount = float(row.get("eligible_amount") or 0)
    item = itc_service.claim(context.org_id, itc_id=itc_id, claimed_amount=amount, actor_id=context.user_id)
    return {"request_id": context.request_id, "item": item}
