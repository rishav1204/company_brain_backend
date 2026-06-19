from __future__ import annotations

import re

from app.modules.platform.governance.utils.field_crypto import encrypt_field
from app.modules.erp.banking.repositories.beneficiary_repository import beneficiary_repository
from app.modules.erp.accounts_payable.repositories.vendor_bank_repository import vendor_bank_repository

IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$", re.IGNORECASE)


class BeneficiaryService:
    def create(self, org_id: str, *, beneficiary_name: str, account_number: str, ifsc_code: str, bank_name: str | None = None, vendor_id: str | None = None, customer_id: str | None = None) -> dict:
        if not IFSC_RE.match(ifsc_code.strip()):
            raise ValueError("Invalid IFSC code")
        return beneficiary_repository.create(org_id, beneficiary_name=beneficiary_name, account_number_encrypted=encrypt_field(account_number.strip()), ifsc_code=ifsc_code.upper(), bank_name=bank_name, vendor_id=vendor_id, customer_id=customer_id, verified=False)

    def list(self, org_id: str, *, vendor_id: str | None = None, verified_only: bool = False) -> list[dict]:
        return beneficiary_repository.list(org_id, vendor_id=vendor_id, verified_only=verified_only)

    def verify(self, org_id: str, *, beneficiary_id: str) -> dict:
        row = beneficiary_repository.get(org_id, beneficiary_id)
        if not row:
            return {"verified": False, "reason": "Beneficiary not found"}
        if not str(row.get("ifsc_code") or "").strip():
            return {"verified": False, "reason": "IFSC missing"}
        beneficiary_repository.set_verified(org_id, beneficiary_id, verified=True)
        return {"verified": True, "beneficiary_id": beneficiary_id}

    def verify_vendor_bank(self, org_id: str, *, vendor_id: str, vendor_bank_account_id: str) -> dict:
        row = vendor_bank_repository.get(org_id, bank_account_id=vendor_bank_account_id)
        if not row:
            return {"verified": False, "reason": "Vendor bank account not found"}
        if str(row.get("vendor_id")) != str(vendor_id):
            return {"verified": False, "reason": "Bank account does not belong to vendor"}
        if not row.get("verified"):
            return {"verified": False, "reason": "Vendor bank account not verified"}
        return {"verified": True, "vendor_bank_account_id": vendor_bank_account_id, "ifsc_code": row.get("ifsc_code")}

    def sync_from_vendor_bank(self, org_id: str, *, vendor_bank_account_id: str) -> dict:
        row = vendor_bank_repository.get(org_id, bank_account_id=vendor_bank_account_id)
        if not row:
            raise ValueError("Vendor bank account not found")
        return beneficiary_repository.create(org_id, beneficiary_name=row.get("bank_name") or "Vendor Beneficiary", account_number_encrypted=row["account_number_encrypted"], ifsc_code=row["ifsc_code"], bank_name=row.get("bank_name"), vendor_id=str(row.get("vendor_id")), verified=bool(row.get("verified")), metadata={"synced_from": vendor_bank_account_id})


beneficiary_service = BeneficiaryService()
