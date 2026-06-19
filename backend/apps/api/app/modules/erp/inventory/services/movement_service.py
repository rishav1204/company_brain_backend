from __future__ import annotations

from datetime import date

from app.modules.erp.inventory.engine.movement_engine import transfer_quantities
from app.modules.erp.inventory.events.inventory_events import emit_inventory_transferred
from app.modules.erp.inventory.repositories.item_repository import item_repository
from app.modules.erp.inventory.repositories.movement_repository import balance_repository, movement_repository


class MovementService:
    def list_movements(
        self,
        org_id: str,
        *,
        item_id: str | None = None,
        warehouse_id: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        return movement_repository.list(org_id, item_id=item_id, warehouse_id=warehouse_id, limit=limit)

    def transfer(
        self,
        org_id: str,
        *,
        item_id: str,
        from_warehouse_id: str,
        to_warehouse_id: str,
        quantity: float,
        movement_date: str | None = None,
        actor_id: str | None = None,
    ) -> dict:
        if from_warehouse_id == to_warehouse_id:
            raise ValueError("Source and destination warehouse must differ")
        item = item_repository.get(org_id, item_id=item_id)
        if not item:
            raise ValueError("Item not found")
        out_qty, in_qty = transfer_quantities(qty=quantity)
        src = balance_repository.get(org_id, item_id=item_id, warehouse_id=from_warehouse_id) or {
            "quantity_on_hand": 0,
            "inventory_value": 0,
            "weighted_avg_cost": 0,
        }
        qty_on_hand = float(src.get("quantity_on_hand") or 0)
        if qty_on_hand < quantity:
            raise ValueError("Insufficient stock for transfer")
        unit_cost = float(src.get("weighted_avg_cost") or 0)
        total_cost = round(quantity * unit_cost, 2)
        mdate = str(movement_date or date.today().isoformat())[:10]

        out_movement = movement_repository.create(
            org_id,
            item_id=item_id,
            warehouse_id=from_warehouse_id,
            movement_type="transfer_out",
            quantity=out_qty,
            unit_cost=unit_cost,
            total_cost=total_cost,
            movement_date=mdate,
            reference_type="transfer",
            reference_id=None,
            created_by=actor_id,
        )
        in_movement = movement_repository.create(
            org_id,
            item_id=item_id,
            warehouse_id=to_warehouse_id,
            movement_type="transfer_in",
            quantity=in_qty,
            unit_cost=unit_cost,
            total_cost=total_cost,
            movement_date=mdate,
            reference_type="transfer",
            reference_id=str(out_movement["id"]),
            created_by=actor_id,
        )

        src_value = round(float(src.get("inventory_value") or 0) - total_cost, 2)
        src_qty = qty_on_hand - quantity
        src_avg = float(src.get("weighted_avg_cost") or 0)
        if src_qty <= 0:
            src_value = 0.0
            src_avg = 0.0
        balance_repository.upsert(
            org_id,
            item_id=item_id,
            warehouse_id=from_warehouse_id,
            quantity_on_hand=src_qty,
            inventory_value=src_value,
            weighted_avg_cost=src_avg,
        )

        dest = balance_repository.get(org_id, item_id=item_id, warehouse_id=to_warehouse_id) or {
            "quantity_on_hand": 0,
            "inventory_value": 0,
            "weighted_avg_cost": 0,
        }
        dest_qty = float(dest.get("quantity_on_hand") or 0) + quantity
        dest_value = round(float(dest.get("inventory_value") or 0) + total_cost, 2)
        dest_avg = round(dest_value / dest_qty, 4) if dest_qty > 0 else unit_cost
        balance_repository.upsert(
            org_id,
            item_id=item_id,
            warehouse_id=to_warehouse_id,
            quantity_on_hand=dest_qty,
            inventory_value=dest_value,
            weighted_avg_cost=dest_avg,
        )
        emit_inventory_transferred(
            org_id,
            item_id=item_id,
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
        )
        return {"out_movement": out_movement, "in_movement": in_movement}


movement_service = MovementService()
