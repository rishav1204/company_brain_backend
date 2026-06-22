from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.reporting.schemas.reporting_schema import CashFlowResponse, StatementResponse, TrialBalanceResponse
from app.modules.erp.reporting.security.reporting_guard import require_reporting_read
from app.modules.erp.reporting.services.balance_sheet_service import balance_sheet_service
from app.modules.erp.reporting.services.cash_flow_service import cash_flow_service
from app.modules.erp.reporting.services.pnl_service import pnl_service
from app.modules.erp.reporting.services.trial_balance_service import trial_balance_service
from app.modules.erp.reporting.events.report_events import emit_report_generated
from app.services.repositories import audit_repo

router = APIRouter(tags=["erp-reports-financial"])


@router.get("/trial-balance", response_model=TrialBalanceResponse)
def trial_balance(
    fiscal_period_id: str = Query(...),
    cursor: str | None = None,
    limit: int = 100,
    context=Depends(build_request_context),
) -> TrialBalanceResponse:
    require_reporting_read(context.user)
    item = trial_balance_service.get_from_reporting(
        context.org_id, fiscal_period_id=fiscal_period_id, cursor=cursor, limit=limit
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="report.generated",
        object_ref=f"erp:report:trial_balance:{fiscal_period_id}",
    )
    emit_report_generated(context.org_id, report_type="trial_balance")
    return TrialBalanceResponse(**item)


@router.get("/pnl", response_model=StatementResponse)
def pnl_report(fiscal_period_id: str = Query(...), context=Depends(build_request_context)) -> StatementResponse:
    require_reporting_read(context.user)
    item = pnl_service.get(context.org_id, fiscal_period_id=fiscal_period_id)
    emit_report_generated(context.org_id, report_type="pnl")
    return StatementResponse(**item)


@router.get("/balance-sheet", response_model=StatementResponse)
def balance_sheet_report(fiscal_period_id: str = Query(...), context=Depends(build_request_context)) -> StatementResponse:
    require_reporting_read(context.user)
    item = balance_sheet_service.get(context.org_id, fiscal_period_id=fiscal_period_id)
    emit_report_generated(context.org_id, report_type="balance_sheet")
    return StatementResponse(**item)


@router.get("/cash-flow", response_model=CashFlowResponse)
def cash_flow_report(
    fiscal_period_id: str | None = None,
    context=Depends(build_request_context),
) -> CashFlowResponse:
    require_reporting_read(context.user)
    item = cash_flow_service.get(context.org_id, fiscal_period_id=fiscal_period_id)
    return CashFlowResponse(**item)
