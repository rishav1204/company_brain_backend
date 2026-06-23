from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.erp.gl.schemas.posting_schema import LedgerPostRequest
from app.modules.erp.gl.security.gl_guard import require_finance_gl_admin
from app.modules.erp.journals.services.approval_service import approval_service as journal_approval_service
from app.modules.erp.journals.services.journal_service import journal_service
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.services.object_context import ObjectContext

router = APIRouter()


@router.post("/gl/post")
def post_to_gl(request: LedgerPostRequest, context=Depends(require_finance_gl_admin)) -> dict:
    """Post to GL via journal orchestrator (single accounting truth path)."""
    total_amount = sum(float(line.debit_amount or 0) for line in request.lines)
    decision = evaluate_access(
        org_id=context.org_id,
        user_id=context.user_id,
        roles=context.roles or [],
        action="post_journal",
        object_context=ObjectContext(
            object_type="journal",
            object_id="gl_post",
            amount=total_amount,
            company_id=request.company_id,
        ),
        attrs=context.attrs or {},
        created_by=context.user_id,
        human_approved=bool(getattr(context, "human_approved", False)),
        object_company_id=request.company_id,
        emit_denial_event=True,
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail={"reason": decision.reason, "checks": decision.checks})

    journal_lines = [
        {
            "account_id": line.account_id,
            "debit_amount": float(line.debit_amount or 0),
            "credit_amount": float(line.credit_amount or 0),
            "cost_center_id": line.cost_center_id,
        }
        for line in request.lines
    ]
    idempotency_key = f"gl-post:{getattr(context, 'request_id', None) or uuid.uuid4().hex}"
    journal = journal_service.create_draft(
        context.org_id,
        created_by=context.user_id,
        journal_type="general",
        posting_date=request.posting_date,
        description="GL post via journal orchestrator",
        source_type="gl_post",
        source_id=getattr(context, "request_id", None) or idempotency_key,
        company_id=request.company_id,
        lines=journal_lines,
        idempotency_key=idempotency_key,
    )
    journal_id = str(journal["journal"]["id"])
    journal_approval_service.approve(
        context.org_id,
        journal_id=journal_id,
        approver_id=context.user_id,
        skip_maker_checker=False,
    )
    post_result = posting_orchestrator.post_journal(
        context.org_id,
        journal_id=journal_id,
        posted_by=context.user_id,
    )
    return {"request_id": context.request_id, "item": post_result, "journal_id": journal_id}
