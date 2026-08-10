from __future__ import annotations

from datetime import datetime, timedelta

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

    def check_fuzzy_duplicate(
        self,
        org_id: str,
        *,
        vendor_id: str,
        invoice_number: str,
        total_amount: float,
        invoice_date: str,
        amount_tolerance: float = 1.0,
        day_window: int = 7,
    ) -> dict | None:
        inv_date = datetime.fromisoformat(invoice_date[:10])
        window_start = (inv_date - timedelta(days=day_window)).isoformat()[:10]
        window_end = (inv_date + timedelta(days=day_window)).isoformat()[:10]
        for inv in invoice_repository.list(org_id, vendor_id=vendor_id):
            if str(inv.get("invoice_number") or "").strip().lower() == invoice_number.strip().lower():
                return {"duplicate": True, "reason": "same invoice number", "existing_invoice_id": inv.get("id")}
            inv_d = str(inv.get("invoice_date") or "")[:10]
            if not inv_d or inv_d < window_start or inv_d > window_end:
                continue
            amt = float(inv.get("total_amount") or 0)
            if abs(amt - total_amount) <= amount_tolerance:
                return {
                    "duplicate": True,
                    "reason": f"same vendor, amount within {amount_tolerance}, date within {day_window} days",
                    "existing_invoice_id": inv.get("id"),
                }
        return {"duplicate": False}


duplicate_invoice_service = DuplicateInvoiceService()
