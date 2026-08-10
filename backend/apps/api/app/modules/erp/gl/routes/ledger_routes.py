from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import build_request_context
from app.modules.erp.gl.security.gl_guard import require_finance_gl_admin
from app.modules.erp.gl.services.ledger_service import ledger_service

router = APIRouter()


@router.get("/ledger/entries")
def list_ledger_entries(
    context=Depends(require_finance_gl_admin),
    account_id: str | None = Query(default=None),
    batch_id: str | None = Query(default=None),
    reference_type: str | None = Query(default=None),
    reference_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    from app.modules.erp.security.branch_scope_sql import branch_ids_from_attrs

    items = ledger_service.list_entries(
        context.org_id,
        account_id=account_id,
        batch_id=batch_id,
        reference_type=reference_type,
        reference_id=reference_id,
        branch_ids=branch_ids_from_attrs(context.attrs),
        limit=limit,
        offset=offset,
    )
    return {"request_id": context.request_id, "items": items}

