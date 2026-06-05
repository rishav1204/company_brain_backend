from __future__ import annotations

import uuid

from app.modules.erp.accounts_payable.repositories.vendor_bank_repository import vendor_bank_repository
from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository
from app.modules.erp.accounts_payable.validators.gstin_validator import validate_gstin, validate_pan
from app.modules.platform.events.events.erp_events import emit_vendor_created
from app.modules.platform.governance.utils.field_crypto import encrypt_field


class VendorService:
    def _vendor_code(self) -> str:
        return "VND-" + uuid.uuid4().hex[:8].upper()

    def create_vendor(
        self,
        org_id: str,
        *,
        vendor_name: str,
        gstin: str | None = None,
        pan: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        payment_terms_days: int = 30,
        payable_account_id: str | None = None,
        company_id: str | None = None,
        created_by: str | None = None,
        vendor_code: str | None = None,
        early_payment_discount_rate: float = 0,
        early_payment_discount_days: int = 0,
    ) -> dict:
        validate_gstin(gstin)
        validate_pan(pan)
        if gstin:
            existing = vendor_repository.find_by_gstin(org_id, gstin=gstin)
            if existing:
                raise ValueError(f"Vendor with GSTIN {gstin} already exists")
        vendor_metadata = {}
        if early_payment_discount_rate > 0:
            vendor_metadata["early_payment_discount_rate"] = early_payment_discount_rate
            vendor_metadata["early_payment_discount_days"] = early_payment_discount_days
        vendor = vendor_repository.create(
            org_id,
            vendor_code=vendor_code or self._vendor_code(),
            vendor_name=vendor_name,
            gstin=gstin.upper() if gstin else None,
            pan=pan.upper() if pan else None,
            email=email,
            phone=phone,
            payment_terms_days=payment_terms_days,
            payable_account_id=payable_account_id,
            company_id=company_id,
            created_by=created_by,
            metadata=vendor_metadata or None,
        )
        emit_vendor_created(org_id, vendor_id=str(vendor["id"]))
        self._audit(org_id, vendor_id=str(vendor["id"]), action="vendor.created", actor_id=created_by)
        return vendor

    def get_vendor(self, org_id: str, *, vendor_id: str) -> dict:
        vendor = vendor_repository.get(org_id, vendor_id=vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")
        banks = vendor_bank_repository.list_by_vendor(org_id, vendor_id=vendor_id)
        return {"vendor": vendor, "bank_accounts": banks}

    def list_vendors(self, org_id: str, *, status: str | None = None) -> list[dict]:
        return vendor_repository.list(org_id, status=status)

    def update_vendor(
        self,
        org_id: str,
        *,
        vendor_id: str,
        vendor_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        payment_terms_days: int | None = None,
        payable_account_id: str | None = None,
        early_payment_discount_rate: float | None = None,
        early_payment_discount_days: int | None = None,
        actor_id: str | None = None,
    ) -> dict:
        existing = vendor_repository.get(org_id, vendor_id=vendor_id)
        if not existing:
            raise ValueError("Vendor not found")
        meta = existing.get("metadata") if isinstance(existing.get("metadata"), dict) else {}
        if early_payment_discount_rate is not None:
            meta["early_payment_discount_rate"] = early_payment_discount_rate
        if early_payment_discount_days is not None:
            meta["early_payment_discount_days"] = early_payment_discount_days
        vendor = vendor_repository.update(
            org_id,
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            email=email,
            phone=phone,
            payment_terms_days=payment_terms_days,
            payable_account_id=payable_account_id,
            metadata=meta if (early_payment_discount_rate is not None or early_payment_discount_days is not None) else None,
        )
        self._audit(org_id, vendor_id=vendor_id, action="vendor.updated", actor_id=actor_id)
        return vendor

    def deactivate_vendor(self, org_id: str, *, vendor_id: str, actor_id: str | None = None) -> dict:
        vendor = vendor_repository.update(org_id, vendor_id=vendor_id, status="inactive")
        self._audit(org_id, vendor_id=vendor_id, action="vendor.deactivated", actor_id=actor_id)
        return vendor

    def get_vendor_risk(self, org_id: str, *, vendor_id: str) -> dict:
        from app.modules.erp.accounts_payable.ai.vendor_risk import assess_vendor_risk
        from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
        from app.modules.erp.accounts_payable.repositories.payment_repository import payment_repository

        invoices = invoice_repository.list(org_id, vendor_id=vendor_id, limit=500)
        payments = payment_repository.list(org_id, limit=500)
        vendor_payments = [p for p in payments if str(p.get("vendor_id")) == vendor_id]
        return assess_vendor_risk(org_id, vendor_id=vendor_id, invoices=invoices, payments=vendor_payments)

    def add_bank_account(
        self,
        org_id: str,
        *,
        vendor_id: str,
        account_number: str,
        ifsc_code: str,
        bank_name: str | None = None,
        is_primary: bool = False,
    ) -> dict:
        vendor = vendor_repository.get(org_id, vendor_id=vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")
        encrypted = encrypt_field(account_number)
        return vendor_bank_repository.create(
            org_id,
            vendor_id=vendor_id,
            account_number_encrypted=encrypted,
            ifsc_code=ifsc_code.upper(),
            bank_name=bank_name,
            is_primary=is_primary,
        )

    def _audit(self, org_id: str, *, vendor_id: str, action: str, actor_id: str | None) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="user",
                actor_id=actor_id or "erp.ap",
                action=action,
                object_ref=f"erp:vendor:{vendor_id}",
                entity_type="vendor",
                entity_id=vendor_id,
                source_service="erp.ap",
            )
        except Exception:
            pass


vendor_service = VendorService()
