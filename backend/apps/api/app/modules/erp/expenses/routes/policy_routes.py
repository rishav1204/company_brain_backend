from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.erp.expenses.security.expense_guard import require_expense_policy, require_expense_read
from app.modules.erp.expenses.services.policy_service import expense_policy_service

router = APIRouter()


@router.get("/policies")
def list_policies(context=Depends(require_expense_read)) -> dict:
    items = expense_policy_service.list_policies(context.org_id)
    return {"request_id": context.request_id, "items": items}
