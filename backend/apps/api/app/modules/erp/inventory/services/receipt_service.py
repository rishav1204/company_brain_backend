from __future__ import annotations

from app.modules.erp.inventory.services.inventory_service import inventory_service


class ReceiptService:
    def receive_from_grn(self, org_id: str, *, grn_id: str, actor_id: str | None = None) -> list[dict]:
        return inventory_service.receive_from_grn(org_id, grn_id=grn_id, actor_id=actor_id)

    def receive_manual(
        self,
        org_id: str,
        *,
        item_id: str,
        warehouse_id: str,
        quantity: float,
        unit_cost: float,
        movement_date: str | None = None,
        actor_id: str | None = None,
        post_journal: bool = True,
    ) -> dict:
        return inventory_service.receive_manual(
            org_id,
            item_id=item_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            unit_cost=unit_cost,
            movement_date=movement_date,
            actor_id=actor_id,
            post_journal=post_journal,
        )


receipt_service = ReceiptService()
