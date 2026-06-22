from __future__ import annotations

from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created


class VoucherWorkflowService:
    def start(self, org_id: str, *, voucher_id: str, amount: float, started_by: str) -> dict | None:
        return handle_entity_created(
            org_id=org_id,
            payload={
                "entity_type": "voucher",
                "entity_id": voucher_id,
                "amount": amount,
                "started_by": started_by,
                "metadata": {"voucher_id": voucher_id},
            },
        )


voucher_workflow_service = VoucherWorkflowService()
