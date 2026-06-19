from __future__ import annotations

from app.modules.erp.banking.repositories.payment_request_repository import payment_request_repository


class PaymentStatusService:
    ALLOWED = {
        "draft": {"pending_approval", "cancelled"},
        "pending_approval": {"approved", "cancelled"},
        "approved": {"processing", "cancelled"},
        "processing": {"completed", "failed"},
        "failed": {"approved"},
        "completed": set(),
        "cancelled": set(),
    }

    def transition(self, org_id: str, *, payment_request_id: str, new_status: str, **kwargs) -> dict:
        row = payment_request_repository.get(org_id, payment_request_id=payment_request_id)
        if not row:
            raise ValueError("Payment request not found")
        current = str(row.get("status"))
        if new_status not in self.ALLOWED.get(current, set()):
            raise ValueError(f"Cannot transition from {current} to {new_status}")
        return payment_request_repository.set_status(org_id, payment_request_id=payment_request_id, status=new_status, **kwargs)


payment_status_service = PaymentStatusService()
