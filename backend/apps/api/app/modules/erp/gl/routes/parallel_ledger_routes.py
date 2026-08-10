from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.erp.gl.schemas.parallel_ledger_schema import (
    MirrorBatchRequest,
    MirrorJournalRequest,
    ParallelLedgerCreateRequest,
)
from app.modules.erp.gl.security.gl_guard import require_finance_gl_admin
from app.modules.erp.gl.services.parallel_ledger_service import parallel_ledger_service

router = APIRouter()


@router.post("/parallel-ledgers")
def create_parallel_ledger(request: ParallelLedgerCreateRequest, context=Depends(require_finance_gl_admin)) -> dict:
    try:
        item = parallel_ledger_service.create_ledger(
            context.org_id,
            ledger_code=request.ledger_code,
            ledger_name=request.ledger_name,
            accounting_standard=request.accounting_standard,
            company_id=request.company_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/parallel-ledgers")
def list_parallel_ledgers(
    context=Depends(require_finance_gl_admin),
    active_only: bool = Query(default=True),
) -> dict:
    items = parallel_ledger_service.list_ledgers(context.org_id, active_only=active_only)
    return {"request_id": context.request_id, "items": items}


@router.get("/parallel-ledgers/{ledger_id}")
def get_parallel_ledger(ledger_id: str, context=Depends(require_finance_gl_admin)) -> dict:
    try:
        item = parallel_ledger_service.get_ledger(context.org_id, ledger_id=ledger_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/parallel-ledgers/{ledger_id}/mirror")
def mirror_journal_to_parallel_ledger(
    ledger_id: str, request: MirrorJournalRequest, context=Depends(require_finance_gl_admin)
) -> dict:
    try:
        item = parallel_ledger_service.mirror_journal(
            context.org_id, parallel_ledger_id=ledger_id, journal_id=request.journal_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/parallel-ledgers/{ledger_id}/mirror-batch")
def mirror_posted_journals_batch(
    ledger_id: str, request: MirrorBatchRequest, context=Depends(require_finance_gl_admin)
) -> dict:
    try:
        item = parallel_ledger_service.mirror_posted_journals(
            context.org_id, parallel_ledger_id=ledger_id, limit=request.limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/parallel-ledgers/{ledger_id}/entries")
def list_parallel_ledger_entries(
    ledger_id: str,
    context=Depends(require_finance_gl_admin),
    source_journal_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict:
    items = parallel_ledger_service.list_entries(
        context.org_id,
        parallel_ledger_id=ledger_id,
        source_journal_id=source_journal_id,
        limit=limit,
    )
    return {"request_id": context.request_id, "items": items}
