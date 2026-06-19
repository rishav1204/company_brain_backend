from __future__ import annotations

from fastapi import HTTPException

from app.modules.core.iam.services.access_control import evaluate_access
from app.services.object_context import ObjectContext


def enforce_tax_action(
    context,
    *,
    action: str,
    object_type: str,
    object_id: str,
    amount: float | None = None,
    created_by: str | None = None,
    company_id: str | None = None,
    human_approved: bool = False,
) -> None:
    decision = evaluate_access(
        org_id=context.org_id,
        user_id=context.user_id,
        roles=context.roles or [],
        action=action,
        object_context=ObjectContext(
            object_type=object_type,
            object_id=object_id,
            amount=amount,
            owner_user_id=created_by,
            company_id=company_id,
        ),
        attrs=context.attrs or {},
        created_by=created_by,
        human_approved=human_approved,
        object_company_id=company_id,
    )
    if not decision.allowed:
        raise HTTPException(status_code=403, detail=decision.reason or "Access denied")
