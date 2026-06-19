from __future__ import annotations

from app.modules.erp.accounts_payable.repositories.vendor_bank_repository import vendor_bank_repository


class BeneficiaryVerificationService:
    def verify_vendor_payment(
        self,
        org_id: str,
        *,
        vendor_id: str,
        vendor_bank_account_id: str | None,
    ) -> dict:
        if not vendor_bank_account_id:
            return {"verified": False, "reason": "vendor_bank_account_id required"}
        row = vendor_bank_repository.get(org_id, bank_account_id=vendor_bank_account_id)
        if not row:
            return {"verified": False, "reason": "Vendor bank account not found"}
        if str(row.get("vendor_id")) != str(vendor_id):
            return {"verified": False, "reason": "Bank account does not belong to vendor"}
        if not row.get("verified"):
            return {"verified": False, "reason": "Vendor bank account not verified"}
        if not str(row.get("ifsc_code") or "").strip():
            return {"verified": False, "reason": "IFSC missing"}
        return {
            "verified": True,
            "vendor_bank_account_id": vendor_bank_account_id,
            "ifsc_code": row.get("ifsc_code"),
            "bank_name": row.get("bank_name"),
        }


beneficiary_verification_service = BeneficiaryVerificationService()
