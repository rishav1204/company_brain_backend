from __future__ import annotations

from app.modules.erp.expenses.repositories.receipt_repository import receipt_repository
from app.modules.erp.expenses.validators.duplicate_validator import receipt_hash


class DuplicateDetectionService:
    def check(
        self,
        org_id: str,
        *,
        document_id: str | None,
        amount: float,
        merchant: str,
        expense_date: str,
        employee_id: str,
    ) -> dict:
        h = receipt_hash(
            document_id=document_id, amount=amount, merchant=merchant,
            expense_date=expense_date, employee_id=employee_id,
        )
        existing = receipt_repository.find_by_hash(org_id, receipt_hash=h)
        return {
            "duplicate": existing is not None,
            "receipt_hash": h,
            "existing_receipt_id": existing.get("id") if existing else None,
        }


duplicate_detection_service = DuplicateDetectionService()
