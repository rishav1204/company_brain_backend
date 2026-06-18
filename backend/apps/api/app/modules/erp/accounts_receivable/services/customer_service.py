from __future__ import annotations

import uuid

from app.modules.erp.accounts_receivable.ai.customer_scoring import score_customer
from app.modules.erp.accounts_receivable.repositories.customer_address_repository import customer_address_repository
from app.modules.erp.accounts_receivable.repositories.customer_repository import customer_repository
from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository
from app.modules.erp.accounts_receivable.repositories.receipt_repository import receipt_repository
from app.modules.erp.accounts_receivable.validators.gstin_validator import validate_gstin, validate_pan


class CustomerService:
    def _customer_code(self) -> str:
        return "CUS-" + uuid.uuid4().hex[:8].upper()

    def create_customer(
        self,
        org_id: str,
        *,
        customer_name: str,
        customer_type: str = "corporate",
        gstin: str | None = None,
        pan: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        credit_limit: float = 0,
        payment_terms_days: int = 30,
        receivable_account_id: str | None = None,
        revenue_account_id: str | None = None,
        company_id: str | None = None,
        created_by: str | None = None,
        customer_code: str | None = None,
    ) -> dict:
        validate_gstin(gstin)
        validate_pan(pan)
        customer = customer_repository.create(
            org_id,
            customer_code=customer_code or self._customer_code(),
            customer_name=customer_name,
            customer_type=customer_type,
            gstin=gstin.upper() if gstin else None,
            pan=pan.upper() if pan else None,
            email=email,
            phone=phone,
            credit_limit=credit_limit,
            payment_terms_days=payment_terms_days,
            receivable_account_id=receivable_account_id,
            revenue_account_id=revenue_account_id,
            company_id=company_id,
            created_by=created_by,
        )
        self._audit(org_id, customer_id=str(customer["id"]), action="ar.customer.created", actor_id=created_by)
        return customer

    def get_customer(self, org_id: str, *, customer_id: str) -> dict:
        customer = customer_repository.get(org_id, customer_id=customer_id)
        if not customer:
            raise ValueError("Customer not found")
        addresses = customer_address_repository.list_by_customer(org_id, customer_id=customer_id)
        return {"customer": customer, "addresses": addresses}

    def list_customers(self, org_id: str, *, status: str | None = None) -> list[dict]:
        return customer_repository.list(org_id, status=status)

    def update_customer(
        self,
        org_id: str,
        *,
        customer_id: str,
        customer_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        credit_limit: float | None = None,
        payment_terms_days: int | None = None,
        actor_id: str | None = None,
        require_workflow: bool = False,
    ) -> dict:
        existing = customer_repository.get(org_id, customer_id=customer_id)
        if not existing:
            raise ValueError("Customer not found")
        if credit_limit is not None and float(credit_limit) > float(existing.get("credit_limit") or 0):
            if require_workflow:
                from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

                handle_entity_created(
                    org_id=org_id,
                    payload={
                        "entity_type": "customer_credit",
                        "entity_id": customer_id,
                        "workflow_key": "AR_CREDIT_LIMIT_APPROVAL",
                        "amount": credit_limit,
                        "metadata": {"customer_id": customer_id, "new_credit_limit": credit_limit},
                    },
                )
        customer = customer_repository.update(
            org_id,
            customer_id=customer_id,
            customer_name=customer_name,
            email=email,
            phone=phone,
            credit_limit=credit_limit,
            payment_terms_days=payment_terms_days,
        )
        self._audit(org_id, customer_id=customer_id, action="ar.customer.updated", actor_id=actor_id)
        return customer

    def add_address(
        self,
        org_id: str,
        *,
        customer_id: str,
        address_type: str,
        line1: str,
        line2: str | None = None,
        city: str | None = None,
        state_code: str | None = None,
        postal_code: str | None = None,
        place_of_supply: str | None = None,
        is_primary: bool = False,
    ) -> dict:
        if not customer_repository.get(org_id, customer_id=customer_id):
            raise ValueError("Customer not found")
        return customer_address_repository.create(
            org_id,
            customer_id=customer_id,
            address_type=address_type,
            line1=line1,
            line2=line2,
            city=city,
            state_code=state_code,
            postal_code=postal_code,
            place_of_supply=place_of_supply,
            is_primary=is_primary,
        )

    def get_customer_risk(self, org_id: str, *, customer_id: str) -> dict:
        invoices = ar_invoice_repository.list(org_id, customer_id=customer_id, limit=500)
        receipts = receipt_repository.list(org_id, customer_id=customer_id, limit=500)
        return score_customer(invoices=invoices, receipts=receipts)

    def _audit(self, org_id: str, *, customer_id: str, action: str, actor_id: str | None) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="user",
                actor_id=actor_id or "erp.ar",
                action=action,
                object_ref=f"erp:customer:{customer_id}",
                entity_type="customer",
                entity_id=customer_id,
                source_service="erp.ar",
            )
        except Exception:
            pass


customer_service = CustomerService()
