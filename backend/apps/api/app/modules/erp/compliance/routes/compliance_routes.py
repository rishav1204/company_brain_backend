from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.modules.erp.compliance.ai.compliance_assistant import answer_compliance_question
from app.modules.erp.compliance.ai.filing_advisor import filing_readiness_score
from app.modules.erp.compliance.ai.notice_predictor import predict_notice_risk
from app.modules.erp.compliance.ai.risk_detector import detect_risks
from app.modules.erp.compliance.schemas.compliance_schema import (
    CompleteRequest,
    CopilotRequest,
    ObligationCreate,
    ObligationUpdate,
    PenaltyOverride,
    RuleUpsert,
    WaiveRequest,
)
from app.modules.erp.compliance.security.compliance_guard import require_compliance_admin, require_compliance_read
from app.modules.erp.compliance.services.calendar_service import calendar_service
from app.modules.erp.compliance.services.compliance_dashboard_service import compliance_dashboard_service
from app.modules.erp.compliance.services.compliance_rule_service import compliance_rule_service
from app.modules.erp.compliance.services.obligation_service import obligation_service
from app.modules.erp.compliance.services.penalty_service import penalty_service

router = APIRouter()


@router.get("/calendar")
def calendar(context=Depends(require_compliance_read), status: str | None = Query(default=None), year: int | None = None, month: int | None = None) -> dict:
    if year and month:
        view = calendar_service.month_view(context.org_id, year=year, month=month)
        return {"request_id": context.request_id, **view}
    items = calendar_service.list(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items}


@router.get("/calendar/upcoming")
def upcoming(context=Depends(require_compliance_read), within_days: int = Query(default=7, ge=1, le=90)) -> dict:
    items = calendar_service.upcoming(context.org_id, within_days=within_days)
    return {"request_id": context.request_id, "items": items}


@router.post("/calendar/seed")
def seed_calendar(context=Depends(require_compliance_admin)) -> dict:
    item = calendar_service.seed_period(context.org_id)
    return {"request_id": context.request_id, "item": item}


@router.get("/obligations")
def list_obligations(
    context=Depends(require_compliance_read),
    status: str | None = None,
    priority: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict:
    items = obligation_service.list(context.org_id, status=status, priority=priority, from_date=from_date, to_date=to_date)
    return {"request_id": context.request_id, "items": items}


@router.post("/obligations")
def create_obligation(request: ObligationCreate, context=Depends(require_compliance_admin)) -> dict:
    item = obligation_service.create_custom(
        context.org_id,
        compliance_code=request.compliance_code,
        title=request.title,
        due_date=request.due_date,
        return_period=request.return_period,
        assigned_to=request.assigned_to,
        metadata=request.metadata,
    )
    return {"request_id": context.request_id, "item": item}


@router.patch("/obligations/{obligation_id}")
def update_obligation(obligation_id: str, request: ObligationUpdate, context=Depends(require_compliance_admin)) -> dict:
    fields = request.model_dump(exclude_none=True)
    item = obligation_service.update(context.org_id, obligation_id, actor_id=context.user_id, **fields)
    return {"request_id": context.request_id, "item": item}


@router.post("/complete")
def complete_obligation(request: CompleteRequest, context=Depends(require_compliance_admin)) -> dict:
    item = obligation_service.complete(context.org_id, request.obligation_id, actor_id=context.user_id)
    return {"request_id": context.request_id, "item": item}


@router.post("/waive")
def waive_obligation(request: WaiveRequest, context=Depends(require_compliance_admin)) -> dict:
    item = obligation_service.waive(context.org_id, request.obligation_id, reason=request.reason, actor_id=context.user_id)
    return {"request_id": context.request_id, "item": item}


@router.get("/dashboard")
def dashboard(context=Depends(require_compliance_read)) -> dict:
    item = compliance_dashboard_service.build(context.org_id)
    return {"request_id": context.request_id, "item": item}


@router.get("/types")
def list_types(context=Depends(require_compliance_read)) -> dict:
    items = compliance_rule_service.list_types()
    return {"request_id": context.request_id, "items": items}


@router.get("/rules")
def list_rules(context=Depends(require_compliance_read)) -> dict:
    items = compliance_rule_service.list_rules(context.org_id)
    return {"request_id": context.request_id, "items": items}


@router.post("/rules")
def upsert_rule(request: RuleUpsert, context=Depends(require_compliance_admin)) -> dict:
    item = compliance_rule_service.upsert_rule(context.org_id, **request.model_dump())
    return {"request_id": context.request_id, "item": item}


@router.post("/rules/seed")
def seed_rules(context=Depends(require_compliance_admin)) -> dict:
    item = compliance_rule_service.seed_defaults(context.org_id)
    return {"request_id": context.request_id, "item": item}


@router.get("/risk")
def compliance_risk(context=Depends(require_compliance_read)) -> dict:
    obligations = obligation_service.list(context.org_id)
    from app.modules.erp.compliance.services.escalation_service import escalation_service

    escalations = escalation_service.list_open(context.org_id)
    exposure = penalty_service.total_exposure(context.org_id)
    item = detect_risks(obligations=obligations, escalations=escalations, exposure=exposure)
    notice = predict_notice_risk(risk_flags=item.get("flags") or [])
    item["notice_prediction"] = notice
    return {"request_id": context.request_id, "item": item}


@router.get("/readiness")
def readiness(context=Depends(require_compliance_read), period: str | None = Query(default=None)) -> dict:
    from app.modules.erp.tax.services.gst_return_service import gst_return_service
    from app.modules.erp.tax.services.gst_reconciliation_service import gst_reconciliation_service
    from app.modules.erp.tax.services.tds_return_service import tds_return_service
    from app.modules.erp.tax.services.tds_service import tds_service

    obligations = obligation_service.list(context.org_id)
    item = filing_readiness_score(
        gst_returns=gst_return_service.list_returns(context.org_id),
        tds_returns=tds_return_service.list_returns(context.org_id),
        tds_liability=tds_service.liability_summary(context.org_id),
        reconciliations=gst_reconciliation_service.list_reconciliations(context.org_id),
        obligations=obligations,
    )
    item["period"] = period
    return {"request_id": context.request_id, "item": item}


@router.post("/copilot")
def copilot(request: CopilotRequest, context=Depends(require_compliance_read)) -> dict:
    dashboard = compliance_dashboard_service.build(context.org_id)
    obligations = obligation_service.list(context.org_id)
    item = answer_compliance_question(question=request.question, obligations=obligations, dashboard=dashboard)
    return {"request_id": context.request_id, "item": item}


@router.post("/penalties/{penalty_id}/override")
def override_penalty(penalty_id: str, request: PenaltyOverride, context=Depends(require_compliance_admin)) -> dict:
    item = penalty_service.override(context.org_id, penalty_id, penalty_amount=request.penalty_amount, interest_amount=request.interest_amount)
    return {"request_id": context.request_id, "item": item}
