from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.erp.journals.schemas.reversal_schema import JournalReverseRequest
from app.modules.erp.journals.security.journal_guard import require_finance_journal_admin
from app.modules.erp.journals.services.journal_service import journal_service
from app.modules.erp.journals.services.reversal_service import journal_reversal_service
from app.services.object_context import ObjectContext

router = APIRouter()


@router.post("/reversals/{journal_id}")
def reverse_journal(
    journal_id: str,
    request: JournalReverseRequest,
    context=Depends(require_finance_journal_admin),
) -> dict:
    journal = journal_service.get(context.org_id, journal_id=journal_id)
    total = sum(float(l.get("debit_amount") or 0) for l in journal.get("lines", []))
    decision = evaluate_access(
        org_id=context.org_id,
        user_id=context.user_id,
        roles=context.roles or [],
        action="journal.post",
        object_context=ObjectContext(
            object_type="journal",
            object_id=journal_id,
            amount=total,
            owner_user_id=journal.get("journal", {}).get("created_by"),
        ),
        attrs=context.attrs or {},
        created_by=journal.get("journal", {}).get("created_by"),
        human_approved=True,
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail={"reason": decision.reason, "checks": decision.checks})
    try:
        item = journal_reversal_service.reverse(
            context.org_id,
            journal_id=journal_id,
            reversed_by=context.user_id,
            reversal_reason=request.reversal_reason,
            approver_id=request.approver_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
