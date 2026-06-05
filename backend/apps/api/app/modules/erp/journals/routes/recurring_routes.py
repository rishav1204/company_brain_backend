from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import build_request_context
from app.modules.erp.journals.schemas.recurring_schema import RecurringJournalCreateRequest
from app.modules.erp.journals.security.journal_guard import require_finance_journal_admin
from app.modules.erp.journals.services.recurring_journal_service import recurring_journal_service

router = APIRouter()


@router.post("/journals/recurring")
def create_recurring_template(request: RecurringJournalCreateRequest, context=Depends(require_finance_journal_admin)) -> dict:
    try:
        item = recurring_journal_service.create_template(
            context.org_id,
            template_name=request.template_name,
            frequency=request.frequency,
            next_run_date=request.next_run_date,
            journal_template=request.journal_template,
            company_id=request.company_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/journals/recurring")
def list_recurring_templates(
    context=Depends(build_request_context),
    active_only: bool = Query(default=True),
) -> dict:
    items = recurring_journal_service.list_templates(context.org_id, active_only=active_only)
    return {"request_id": context.request_id, "items": items}


@router.post("/journals/recurring/{recurring_id}/deactivate")
def deactivate_recurring(recurring_id: str, context=Depends(require_finance_journal_admin)) -> dict:
    item = recurring_journal_service.deactivate(context.org_id, recurring_id=recurring_id)
    return {"request_id": context.request_id, "item": item}


@router.post("/journals/recurring/run-due")
def run_due_recurring(context=Depends(require_finance_journal_admin), as_of_date: str | None = Query(default=None)) -> dict:
    items = recurring_journal_service.run_due(context.org_id, as_of_date=as_of_date)
    return {"request_id": context.request_id, "items": items}
