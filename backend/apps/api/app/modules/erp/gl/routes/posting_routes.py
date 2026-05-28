from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.core.iam.services.access_control import evaluate_access
from app.modules.erp.gl.schemas.posting_schema import LedgerPostRequest
from app.modules.erp.gl.security.gl_guard import require_finance_gl_admin
from app.modules.erp.gl.services.posting_service import posting_service
from app.services.object_context import ObjectContext

router = APIRouter()


@router.post("/gl/post")
def post_to_gl(request: LedgerPostRequest, context=Depends(require_finance_gl_admin)) -> dict:
    # Enforce IAM policy + maker-checker rules consistently with rest of platform.
    total_amount = sum(float(l.debit_amount or 0) for l in request.lines)
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

    item = posting_service.post(
        context.org_id,
        posted_by=context.user_id,
        posting_date=request.posting_date,
        company_id=request.company_id,
        lines=[l.model_dump() for l in request.lines],
    )
    return {"request_id": context.request_id, "item": item}

