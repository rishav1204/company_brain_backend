from __future__ import annotations

from app.modules.erp.accounts_payable.services.invoice_service import invoice_service


class ApApprovalService:
    def submit_invoice(self, org_id: str, *, invoice_id: str, actor_id: str | None) -> dict:
        return invoice_service.submit_for_approval(org_id, invoice_id=invoice_id, actor_id=actor_id)

    def approve_invoice(
        self,
        org_id: str,
        *,
        invoice_id: str,
        approver_id: str,
        expense_account_id: str | None = None,
        auto_post: bool = False,
    ) -> dict:
        return invoice_service.approve(
            org_id,
            invoice_id=invoice_id,
            approver_id=approver_id,
            expense_account_id=expense_account_id,
            auto_post=auto_post,
        )


ap_approval_service = ApApprovalService()
