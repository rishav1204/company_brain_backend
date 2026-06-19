from __future__ import annotations

from datetime import date

from app.modules.erp.accounts_payable.engine.account_resolver import resolve_expense_account
from app.modules.erp.expenses.ai.expense_classifier import classify_expense
from app.modules.erp.expenses.ai.fraud_detector import detect as detect_fraud
from app.modules.erp.expenses.repositories.receipt_repository import receipt_repository
from app.modules.erp.expenses.services.claim_service import claim_service
from app.modules.erp.expenses.services.duplicate_detection_service import duplicate_detection_service
from app.modules.erp.expenses.validators.duplicate_validator import receipt_hash
from app.modules.erp.expenses.events.expense_events import emit_receipt_extracted


class AiExpenseService:
    def create_from_extraction(
        self,
        org_id: str,
        *,
        extracted_data: dict,
        source_document_id: str | None = None,
        employee_id: str,
        created_by: str | None = None,
        company_id: str | None = None,
    ) -> dict:
        merchant = str(extracted_data.get("merchant") or extracted_data.get("vendor") or "Unknown")
        amount = float(extracted_data.get("amount") or extracted_data.get("total_amount") or extracted_data.get("total") or 0)
        expense_date = str(extracted_data.get("date") or extracted_data.get("receipt_date") or extracted_data.get("invoice_date") or date.today().isoformat())[:10]
        expense_type = classify_expense(extracted_data)
        dup = duplicate_detection_service.check(
            org_id, document_id=source_document_id, amount=amount,
            merchant=merchant, expense_date=expense_date, employee_id=employee_id,
        )
        if dup.get("duplicate"):
            raise ValueError(f"Duplicate receipt detected: {dup.get('existing_receipt_id')}")
        fraud = detect_fraud(extracted_data, amount=amount)
        h = receipt_hash(
            document_id=source_document_id, amount=amount, merchant=merchant,
            expense_date=expense_date, employee_id=employee_id,
        )
        receipt = receipt_repository.create(
            org_id,
            document_id=source_document_id,
            merchant_name=merchant,
            receipt_date=expense_date,
            receipt_amount=amount,
            confidence_score=float(extracted_data.get("confidence_score") or 0),
            receipt_hash=h,
            ocr_status="completed",
            metadata={"fraud": fraud, "expense_type": expense_type},
        )
        claim = claim_service.create(
            org_id,
            employee_id=employee_id,
            claim_date=expense_date,
            expense_category=expense_type,
            company_id=company_id,
            created_by=created_by or employee_id,
            items=[{
                "expense_date": expense_date,
                "expense_type": expense_type,
                "amount": amount,
                "merchant_name": merchant,
                "description": extracted_data.get("description"),
                "receipt_id": receipt["id"],
                "expense_account_id": resolve_expense_account(org_id, extracted_data),
            }],
        )
        emit_receipt_extracted(org_id, document_id=source_document_id or "", claim_id=str(claim.get("id")))
        return claim


ai_expense_service = AiExpenseService()
