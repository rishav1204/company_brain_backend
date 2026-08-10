from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import build_request_context
from app.modules.erp.journals.schemas.journal_schema import (
    AiJournalFromDocumentRequest,
    JournalCreateRequest,
    JournalUpdateRequest,
)
from app.modules.erp.journals.security.journal_guard import require_finance_journal_admin
from app.modules.erp.journals.services.ai_journal_service import ai_journal_service
from app.modules.erp.journals.services.journal_service import journal_service

router = APIRouter()


@router.post("/journals")
def create_journal(request: JournalCreateRequest, context=Depends(require_finance_journal_admin)) -> dict:
    try:
        item = journal_service.create_draft(
            context.org_id,
            created_by=context.user_id,
            journal_type=request.journal_type,
            posting_date=request.posting_date,
            description=request.description,
            source_type=request.source_type,
            source_id=request.source_id,
            currency_code=request.currency_code,
            exchange_rate=request.exchange_rate,
            company_id=request.company_id,
            lines=[l.model_dump() for l in request.lines],
            idempotency_key=request.idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/journals")
def list_journals(
    context=Depends(build_request_context),
    journal_status: str | None = Query(default=None),
    journal_type: str | None = Query(default=None),
    company_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    from app.modules.erp.security.branch_scope_sql import branch_ids_from_attrs

    items = journal_service.list(
        context.org_id,
        journal_status=journal_status,
        journal_type=journal_type,
        company_id=company_id,
        branch_ids=branch_ids_from_attrs(context.attrs),
        limit=limit,
        offset=offset,
    )
    return {"request_id": context.request_id, "items": items}


@router.get("/journals/{journal_id}")
def get_journal(journal_id: str, context=Depends(build_request_context)) -> dict:
    try:
        item = journal_service.get(context.org_id, journal_id=journal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.put("/journals/{journal_id}")
def update_journal(
    journal_id: str,
    request: JournalUpdateRequest,
    context=Depends(require_finance_journal_admin),
) -> dict:
    try:
        item = journal_service.update_draft(
            context.org_id,
            journal_id=journal_id,
            posting_date=request.posting_date,
            description=request.description,
            journal_type=request.journal_type,
            lines=[l.model_dump() for l in request.lines] if request.lines is not None else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/journals/{journal_id}/cancel")
def cancel_journal(journal_id: str, context=Depends(require_finance_journal_admin)) -> dict:
    try:
        item = journal_service.cancel(context.org_id, journal_id=journal_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/journals/ai/from-document")
def create_ai_draft_journal(request: AiJournalFromDocumentRequest, context=Depends(require_finance_journal_admin)) -> dict:
    try:
        item = ai_journal_service.create_draft_from_extraction(
            context.org_id,
            created_by=context.user_id,
            document_id=request.document_id,
            extracted_data=request.extracted_data,
            posting_date=request.posting_date,
            journal_type=request.journal_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
