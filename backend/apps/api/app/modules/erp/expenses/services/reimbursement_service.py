from __future__ import annotations

from app.modules.erp.expenses.engine.account_resolver import resolve_employee_payable_account
from app.modules.erp.expenses.repositories.claim_repository import claim_repository
from app.modules.erp.expenses.events.expense_events import emit_reimbursement_scheduled, emit_reimbursed


class ReimbursementService:
    def schedule(
        self,
        org_id: str,
        *,
        claim_id: str,
        actor_id: str,
        bank_account_id: str | None = None,
    ) -> dict:
        claim = claim_repository.get(org_id, claim_id=claim_id)
        if not claim:
            raise ValueError("Claim not found")
        if str(claim.get("status")) != "approved":
            raise ValueError("Only approved claims can be reimbursed")
        payable_id = resolve_employee_payable_account(org_id)
        if not payable_id:
            raise ValueError("Employee payable account not configured")
        amount = float(claim.get("total_amount") or 0)
        from app.modules.erp.treasury.services.payment_service import treasury_payment_service
        from app.modules.erp.treasury.services.bank_account_service import bank_account_service

        if not bank_account_id:
            accounts = bank_account_service.list_accounts(org_id, active_only=True)
            bank_account_id = str(accounts[0]["id"]) if accounts else None
        if not bank_account_id:
            raise ValueError("Bank account required for reimbursement")

        req = treasury_payment_service.create_request(
            org_id,
            payment_type="reimbursement",
            beneficiary_type="employee",
            beneficiary_ref=str(claim["employee_id"]),
            bank_account_id=bank_account_id,
            amount=amount,
            currency_code="INR",
            scheduled_date=str(claim.get("claim_date") or "")[:10] or None,
            source_type="expense_claim",
            source_id=claim_id,
            company_id=claim.get("company_id"),
            created_by=actor_id,
            metadata={"liability_account_id": payable_id, "claim_id": claim_id},
            start_workflow=True,
        )
        pr_id = str(req.get("payment_request_id") or req.get("id") or "")
        claim_repository.set_status(org_id, claim_id=claim_id, status="approved", reimbursement_payment_id=pr_id)
        emit_reimbursement_scheduled(org_id, claim_id=claim_id, payment_request_id=pr_id)
        return req

    def mark_workflow_approved(self, org_id: str, *, payment_request_id: str) -> dict:
        from app.modules.erp.treasury.services.payment_service import treasury_payment_service

        return treasury_payment_service.mark_workflow_approved(org_id, payment_request_id=payment_request_id)

    def execute(self, org_id: str, *, payment_request_id: str, actor_id: str) -> dict:
        from app.modules.erp.treasury.services.payment_service import treasury_payment_service

        result = treasury_payment_service.execute_request(org_id, payment_request_id=payment_request_id, executed_by=actor_id)
        meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
        claim_id = str(meta.get("claim_id") or result.get("source_id") or "")
        if claim_id:
            claim_repository.set_status(org_id, claim_id=claim_id, status="paid", reimbursement_payment_id=payment_request_id)
            emit_reimbursed(org_id, claim_id=claim_id, payment_request_id=payment_request_id)
        return result

    def on_payment_executed(self, org_id: str, *, source_id: str, payment_request_id: str) -> None:
        claim = claim_repository.get(org_id, claim_id=source_id)
        if claim and str(claim.get("status")) == "approved":
            claim_repository.set_status(org_id, claim_id=source_id, status="paid", reimbursement_payment_id=payment_request_id)
            emit_reimbursed(org_id, claim_id=source_id, payment_request_id=payment_request_id)


reimbursement_service = ReimbursementService()
