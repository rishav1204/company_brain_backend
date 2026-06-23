from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.modules.erp.banking.ai.banking_copilot import answer_banking_question
from app.modules.erp.banking.schemas.banking_schema import (
    BankAccountCreateRequest,
    BankAccountUpdateRequest,
    BankFeedSyncRequest,
    BankTransactionImportRequest,
    BeneficiaryCreateRequest,
    BankingCopilotRequest,
    PaymentExecuteRequest,
    PaymentRequestCreate,
    ReceiptCreateRequest,
)
from app.modules.erp.banking.security.banking_guard import require_banking_admin, require_banking_read
from app.modules.erp.banking.services.bank_account_service import bank_account_service
from app.modules.erp.banking.services.bank_feed_service import bank_feed_service
from app.modules.erp.banking.services.beneficiary_service import beneficiary_service
from app.modules.erp.banking.services.payment_execution_service import payment_execution_service
from app.modules.erp.banking.services.receipt_service import receipt_service
from app.modules.erp.banking.services.statement_import_service import statement_import_service
from app.modules.erp.banking.services.transaction_service import transaction_service

router = APIRouter()


@router.post("/accounts")
def create_account(request: BankAccountCreateRequest, context=Depends(require_banking_admin)) -> dict:
    try:
        item = bank_account_service.create_account(context.org_id, account_name=request.account_name, bank_name=request.bank_name, account_number=request.account_number, ifsc_code=request.ifsc_code, currency_code=request.currency_code, account_type=request.account_type, ledger_account_id=request.ledger_account_id, company_id=request.company_id, created_by=context.user_id, opening_balance=request.opening_balance)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/accounts")
def list_accounts(context=Depends(require_banking_read)) -> dict:
    return {"request_id": context.request_id, "items": bank_account_service.list_accounts(context.org_id)}


@router.get("/accounts/{bank_account_id}")
def get_account(bank_account_id: str, context=Depends(require_banking_read)) -> dict:
    try:
        item = bank_account_service.get_account(context.org_id, bank_account_id=bank_account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.patch("/accounts/{bank_account_id}")
def update_account(bank_account_id: str, request: BankAccountUpdateRequest, context=Depends(require_banking_admin)) -> dict:
    try:
        item = bank_account_service.update_account(context.org_id, bank_account_id=bank_account_id, account_name=request.account_name, is_active=request.is_active, ledger_account_id=request.ledger_account_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


MAX_BANK_STATEMENT_BYTES = 20 * 1024 * 1024


@router.post("/statements/import")
async def import_statement(bank_account_id: str = Form(...), file_format: str = Form(...), file: UploadFile = File(...), context=Depends(require_banking_admin)) -> dict:
    content = await file.read(MAX_BANK_STATEMENT_BYTES + 1)
    if len(content) > MAX_BANK_STATEMENT_BYTES:
        raise HTTPException(status_code=413, detail="Statement file exceeds 20MB limit")
    try:
        item = statement_import_service.import_file(context.org_id, bank_account_id=bank_account_id, file_format=file_format, content=content, imported_by=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/transactions/import")
def import_transactions(request: BankTransactionImportRequest, context=Depends(require_banking_admin)) -> dict:
    try:
        item = bank_feed_service.import_feed(context.org_id, bank_account_id=request.bank_account_id, provider=request.provider, transactions=request.transactions)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/transactions/sync")
def sync_feed(request: BankFeedSyncRequest, context=Depends(require_banking_admin)) -> dict:
    try:
        item = bank_feed_service.import_feed(context.org_id, bank_account_id=request.bank_account_id, provider=request.provider, payload=request.payload, source="bank_feed")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/transactions")
def list_transactions(context=Depends(require_banking_read), bank_account_id: str | None = Query(default=None), reconciliation_status: str | None = Query(default=None)) -> dict:
    return {"request_id": context.request_id, "items": transaction_service.list_transactions(context.org_id, bank_account_id=bank_account_id, reconciliation_status=reconciliation_status)}


@router.post("/payments")
def create_payment(request: PaymentRequestCreate, context=Depends(require_banking_admin)) -> dict:
    meta = {}
    if request.expense_account_id:
        meta["expense_account_id"] = request.expense_account_id
    if request.dest_bank_account_id:
        meta["dest_bank_account_id"] = request.dest_bank_account_id
    if request.vendor_bank_account_id:
        meta["vendor_bank_account_id"] = request.vendor_bank_account_id
    if request.ap_payment_id:
        meta["ap_payment_id"] = request.ap_payment_id
    try:
        item = payment_execution_service.create_request(context.org_id, payment_type=request.payment_type, beneficiary_type=request.beneficiary_type, beneficiary_ref=request.beneficiary_ref, bank_account_id=request.bank_account_id, amount=request.amount, currency_code=request.currency_code, scheduled_date=request.scheduled_date, source_type=request.source_type, source_id=request.source_id, company_id=request.company_id, created_by=context.user_id, metadata=meta, beneficiary_id=request.beneficiary_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/payments")
def list_payments(context=Depends(require_banking_read), status: str | None = Query(default=None)) -> dict:
    return {"request_id": context.request_id, "items": payment_execution_service.list_requests(context.org_id, status=status)}


@router.get("/payments/{payment_request_id}")
def get_payment(payment_request_id: str, context=Depends(require_banking_read)) -> dict:
    try:
        item = payment_execution_service.get_request(context.org_id, payment_request_id=payment_request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/payments/{payment_request_id}/cancel")
def cancel_payment(payment_request_id: str, context=Depends(require_banking_admin)) -> dict:
    try:
        item = payment_execution_service.cancel_request(context.org_id, payment_request_id=payment_request_id, actor_id=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/payments/{payment_request_id}/execute")
def execute_payment(payment_request_id: str, request: PaymentExecuteRequest, context=Depends(require_banking_admin)) -> dict:
    try:
        item = payment_execution_service.execute_request(context.org_id, payment_request_id=payment_request_id, executed_by=context.user_id, auto_post=request.auto_post)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/beneficiaries")
def create_beneficiary(request: BeneficiaryCreateRequest, context=Depends(require_banking_admin)) -> dict:
    try:
        item = beneficiary_service.create(context.org_id, beneficiary_name=request.beneficiary_name, account_number=request.account_number, ifsc_code=request.ifsc_code, bank_name=request.bank_name, vendor_id=request.vendor_id, customer_id=request.customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/beneficiaries")
def list_beneficiaries(context=Depends(require_banking_read), vendor_id: str | None = Query(default=None)) -> dict:
    return {"request_id": context.request_id, "items": beneficiary_service.list(context.org_id, vendor_id=vendor_id)}


@router.post("/beneficiaries/{beneficiary_id}/verify")
def verify_beneficiary(beneficiary_id: str, context=Depends(require_banking_admin)) -> dict:
    item = beneficiary_service.verify(context.org_id, beneficiary_id=beneficiary_id)
    return {"request_id": context.request_id, "item": item}


@router.post("/receipts")
def create_receipt(request: ReceiptCreateRequest, context=Depends(require_banking_admin)) -> dict:
    try:
        item = receipt_service.record(context.org_id, customer_id=request.customer_id, bank_account_id=request.bank_account_id, amount=request.amount, receipt_date=request.receipt_date, payment_mode=request.payment_mode, reference=request.reference)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.post("/receipts/{receipt_id}/complete")
def complete_receipt(receipt_id: str, context=Depends(require_banking_admin)) -> dict:
    try:
        item = receipt_service.complete(context.org_id, receipt_id=receipt_id, completed_by=context.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": item}


@router.get("/receipts")
def list_receipts(context=Depends(require_banking_read), customer_id: str | None = Query(default=None)) -> dict:
    return {"request_id": context.request_id, "items": receipt_service.list(context.org_id, customer_id=customer_id)}


@router.post("/copilot")
def banking_copilot(request: BankingCopilotRequest, context=Depends(require_banking_read)) -> dict:
    payments = payment_execution_service.list_requests(context.org_id)
    transactions = transaction_service.list_transactions(context.org_id)
    item = answer_banking_question(question=request.question, payments=payments, transactions=transactions)
    return {"request_id": context.request_id, "item": item}
