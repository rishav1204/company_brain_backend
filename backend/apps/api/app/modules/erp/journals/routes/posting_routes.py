from __future__ import annotations



from fastapi import APIRouter, Depends, HTTPException, Query



from app.modules.core.iam.services.access_control import evaluate_access

from app.modules.erp.journals.schemas.journal_schema import BatchPostRequest, JournalMarkReviewedRequest

from app.modules.erp.journals.security.journal_guard import require_finance_journal_admin, require_journal_read

from app.modules.erp.journals.services.approval_service import approval_service

from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator

from app.modules.erp.journals.services.journal_service import journal_service

from app.modules.erp.journals.repositories.journal_repository import journal_repository

from app.services.object_context import ObjectContext



router = APIRouter()





def _journal_amount(journal_payload: dict) -> float:

    return sum(float(l.get("debit_amount") or 0) for l in journal_payload.get("lines", []))





def _enforce_journal_action(context, journal_payload: dict, action: str) -> None:

    journal = journal_payload.get("journal", {})

    decision = evaluate_access(

        org_id=context.org_id,

        user_id=context.user_id,

        roles=context.roles or [],

        action=action,

        object_context=ObjectContext(

            object_type="journal",

            object_id=journal.get("id"),

            amount=_journal_amount(journal_payload),

            owner_user_id=journal.get("created_by"),

            company_id=journal.get("company_id"),

        ),

        attrs=context.attrs or {},

        created_by=journal.get("created_by"),

        human_approved=action in {"post_journal", "journal.post"},

        object_company_id=journal.get("company_id"),

    )

    if not decision.allowed:

        raise HTTPException(status_code=403, detail={"reason": decision.reason, "checks": decision.checks})





@router.get("/journals/approval-queue")

def approval_queue(

    context=Depends(require_journal_read),

    limit: int = Query(default=100, ge=1, le=500),

    offset: int = Query(default=0, ge=0),

) -> dict:

    items = approval_service.list_approval_queue(context.org_id, limit=limit, offset=offset)

    return {"request_id": context.request_id, "items": items, "count": len(items)}





@router.post("/journals/{journal_id}/submit")

def submit_journal(journal_id: str, context=Depends(require_finance_journal_admin)) -> dict:

    journal_payload = journal_service.get(context.org_id, journal_id=journal_id)

    _enforce_journal_action(context, journal_payload, "journal.submit")

    try:

        item = approval_service.submit_for_approval(context.org_id, journal_id=journal_id, actor_id=context.user_id)

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"request_id": context.request_id, "item": item}





@router.post("/journals/{journal_id}/approve")

def approve_journal(journal_id: str, context=Depends(require_finance_journal_admin)) -> dict:

    journal_payload = journal_service.get(context.org_id, journal_id=journal_id)

    _enforce_journal_action(context, journal_payload, "approve")

    try:

        item = approval_service.approve(context.org_id, journal_id=journal_id, approver_id=context.user_id)

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"request_id": context.request_id, "item": item}





@router.post("/journals/{journal_id}/reject")

def reject_journal(journal_id: str, context=Depends(require_finance_journal_admin)) -> dict:

    try:

        item = approval_service.reject(context.org_id, journal_id=journal_id, actor_id=context.user_id)

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"request_id": context.request_id, "item": item}





@router.post("/journals/{journal_id}/mark-reviewed")

def mark_journal_reviewed(

    journal_id: str,

    request: JournalMarkReviewedRequest,

    context=Depends(require_finance_journal_admin),

) -> dict:

    journal_repository.clear_ai_review_flag(context.org_id, journal_id=journal_id)

    item = journal_service.get(context.org_id, journal_id=journal_id)

    return {"request_id": context.request_id, "item": item, "comment": request.comment}





@router.post("/postings/{journal_id}/post")

def post_journal(journal_id: str, context=Depends(require_finance_journal_admin)) -> dict:

    journal_payload = journal_service.get(context.org_id, journal_id=journal_id)

    _enforce_journal_action(context, journal_payload, "post_journal")

    try:

        item = posting_orchestrator.post_journal(context.org_id, journal_id=journal_id, posted_by=context.user_id)

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"request_id": context.request_id, "item": item}





@router.post("/postings/batch")

def post_journals_batch(request: BatchPostRequest, context=Depends(require_finance_journal_admin)) -> dict:

    for jid in request.journal_ids:

        journal_payload = journal_service.get(context.org_id, journal_id=jid)

        _enforce_journal_action(context, journal_payload, "post_journal")

    items = posting_orchestrator.post_batch(

        context.org_id,

        journal_ids=request.journal_ids,

        posted_by=context.user_id,

    )

    return {"request_id": context.request_id, "items": items, "count": len(items)}


