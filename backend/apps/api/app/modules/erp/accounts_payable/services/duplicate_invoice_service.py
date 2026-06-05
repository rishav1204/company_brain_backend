from __future__ import annotations

from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
from app.modules.erp.accounts_payable.validators.invoice_validator import build_duplicate_checksum


class DuplicateInvoiceService:
    def check_duplicate(
        self,
        org_id: str,
        *,
        vendor_id: str,
        invoice_number: str,
        total_amount: float,
        invoice_date: str,
    ) -> dict | None:
        checksum = build_duplicate_checksum(
            vendor_id=vendor_id,
            invoice_number=invoice_number,
            total_amount=total_amount,
            invoice_date=invoice_date,
        )
        existing = invoice_repository.find_duplicate(org_id, duplicate_checksum=checksum)
        if existing:
            return {"duplicate": True, "existing_invoice": existing, "checksum": checksum}
        return {"duplicate": False, "checksum": checksum}


duplicate_invoice_service = DuplicateInvoiceService()
