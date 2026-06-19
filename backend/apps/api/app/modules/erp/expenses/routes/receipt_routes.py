from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.modules.erp.expenses.repositories.receipt_repository import receipt_repository
from app.modules.erp.expenses.schemas.expense_schema import ReceiptFromDocumentRequest
from app.modules.erp.expenses.security.expense_guard import require_expense_create, require_expense_read
from app.modules.erp.expenses.services.ai_expense_service import ai_expense_service

router = APIRouter()


@router.get("/receipts/{receipt_id}")
def get_receipt(receipt_id: str, context=Depends(require_expense_read)) -> dict:
    item = receipt_repository.get(context.org_id, receipt_id=receipt_id)
    if not item:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return {"request_id": context.request_id, "item": item}


@router.post("/receipts/from-document")
def create_from_document(request: ReceiptFromDocumentRequest, context=Depends(require_expense_create)) -> dict:
    extracted = request.extracted_data
    if not extracted:
        try:
            from app.modules.platform.documents.repositories.extraction_repository import extraction_repository

            extraction = extraction_repository.latest_extraction(context.org_id, request.document_id) or {}
            extracted = extraction.get("extracted_data") if isinstance(extraction.get("extracted_data"), dict) else {}
        except Exception:
            extracted = {}
    if not extracted:
        raise HTTPException(status_code=400, detail="No extraction data for document")
    try:
        item = ai_expense_service.create_from_extraction(
            context.org_id,
            extracted_data=extracted,
            source_document_id=request.document_id,
            employee_id=request.employee_id or context.user_id,
            created_by=context.user_id,
            company_id=request.company_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}
