from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.modules.erp.tax.ai.compliance_assistant import answer_compliance_question
from app.modules.erp.tax.ai.gst_copilot import answer_gst_question
from app.modules.erp.tax.ai.tds_copilot import answer_tds_question
from app.modules.erp.tax.ai.tax_risk_engine import assess_tax_risks
from app.modules.erp.tax.schemas.tax_schema import ComplianceCopilotRequest, TaxNoticeCreate
from app.modules.erp.tax.security.tax_access import enforce_tax_action
from app.modules.erp.tax.security.tax_guard import require_tax_admin, require_tax_read
from app.modules.erp.tax.services.compliance_calendar_service import compliance_calendar_service
from app.modules.erp.tax.services.gst_reconciliation_service import gst_reconciliation_service
from app.modules.erp.tax.services.gst_return_service import gst_return_service
from app.modules.erp.tax.services.gst_service import gst_service
from app.modules.erp.tax.services.itc_service import itc_service
from app.modules.erp.tax.services.notice_management_service import notice_management_service
from app.modules.erp.tax.services.tds_challan_service import tds_challan_service
from app.modules.erp.tax.services.tds_reconciliation_service import tds_reconciliation_service
from app.modules.erp.tax.services.tds_return_service import tds_return_service
from app.modules.erp.tax.services.tds_service import tds_service

router = APIRouter()


@router.get("/calendar")
def list_calendar(context=Depends(require_tax_read), status: str | None = Query(default=None)) -> dict:
    items = compliance_calendar_service.list_obligations(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.post("/calendar/seed")
def seed_calendar(context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="compliance_calendar", object_id="seed")
    item = compliance_calendar_service.seed_period(context.org_id)
    return {"request_id": context.request_id, "item": item}


@router.get("/calendar/upcoming")
def upcoming_calendar(context=Depends(require_tax_read), within_days: int = Query(default=7, ge=1, le=30)) -> dict:
    items = compliance_calendar_service.check_upcoming(context.org_id, within_days=within_days)
    return {"request_id": context.request_id, "items": items}


@router.post("/notices")
def create_notice(request: TaxNoticeCreate, context=Depends(require_tax_admin)) -> dict:
    enforce_tax_action(context, action="tax.modify", object_type="tax_notice", object_id="new")
    item = notice_management_service.create_notice(
        context.org_id,
        notice_type=request.notice_type,
        received_date=request.received_date,
        document_id=request.document_id,
        metadata=request.metadata,
    )
    return {"request_id": context.request_id, "item": item}


@router.get("/notices")
def list_notices(context=Depends(require_tax_read)) -> dict:
    items = notice_management_service.list_notices(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.get("/risk")
def tax_risk(context=Depends(require_tax_read)) -> dict:
    reconciliations = gst_reconciliation_service.list_reconciliations(context.org_id)
    returns = gst_return_service.list_returns(context.org_id)
    calendar = compliance_calendar_service.list_obligations(context.org_id)
    transactions = gst_service.list_transactions(context.org_id)
    item = assess_tax_risks(
        reconciliations=reconciliations,
        returns=returns,
        calendar=calendar,
        transactions=transactions,
        tds_transactions=tds_service.list_transactions(context.org_id),
        tds_returns=tds_return_service.list_returns(context.org_id),
        tds_liability=tds_service.liability_summary(context.org_id),
        tds_reconciliations=tds_reconciliation_service.list_reconciliations(context.org_id),
    )
    return {"request_id": context.request_id, "item": item}


@router.post("/copilot")
def compliance_copilot(request: ComplianceCopilotRequest, context=Depends(require_tax_read)) -> dict:
    enforce_tax_action(context, action="tax.read", object_type="tax_copilot", object_id="copilot")
    q = request.question.lower()
    if any(k in q for k in ("tds", "challan", "26q", "form 16", "form16", "194")):
        item = answer_tds_question(
            question=request.question,
            liability=tds_service.liability_summary(context.org_id),
            transactions=tds_service.list_transactions(context.org_id),
            returns=tds_return_service.list_returns(context.org_id),
            challans=tds_challan_service.list_challans(context.org_id),
        )
    elif "vendor" in q or "mismatch" in q:
        reconciliations = gst_reconciliation_service.list_reconciliations(context.org_id, match_status="mismatch")
        item = answer_compliance_question(question=request.question, reconciliations=reconciliations)
    else:
        returns = gst_return_service.list_returns(context.org_id)
        transactions = gst_service.list_transactions(context.org_id)
        itc_summary = itc_service.summary(context.org_id)
        item = answer_gst_question(question=request.question, returns=returns, transactions=transactions, itc_summary=itc_summary)
    return {"request_id": context.request_id, "item": item}
