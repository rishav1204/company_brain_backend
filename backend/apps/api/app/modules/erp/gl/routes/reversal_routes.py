from __future__ import annotations

from fastapi import APIRouter, Depends

from app.modules.erp.gl.security.gl_guard import require_finance_gl_admin
from app.modules.erp.gl.services.reversal_service import reversal_service

router = APIRouter()


@router.post("/gl/batches/{batch_id}/reverse")
def reverse_batch(batch_id: str, context=Depends(require_finance_gl_admin)) -> dict:
    item = reversal_service.reverse_batch(context.org_id, batch_id=batch_id, reversed_by=context.user_id)
    return {"request_id": context.request_id, "item": item}

