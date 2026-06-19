from __future__ import annotations

from app.modules.platform.events.services.event_service import platform_event_service


def emit_inventory_received(org_id: str, *, movement_id: str, item_id: str, quantity: float) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="inventory.received",
        source="erp.inventory",
        payload={"movement_id": movement_id, "item_id": item_id, "quantity": quantity},
    )


def emit_inventory_issued(org_id: str, *, movement_id: str, item_id: str, quantity: float, total_cost: float) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="inventory.issued",
        source="erp.inventory",
        payload={"movement_id": movement_id, "item_id": item_id, "quantity": quantity, "total_cost": total_cost},
    )


def emit_inventory_adjusted(org_id: str, *, adjustment_id: str, item_id: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="inventory.adjusted",
        source="erp.inventory",
        payload={"adjustment_id": adjustment_id, "item_id": item_id},
    )


def emit_inventory_transferred(org_id: str, *, item_id: str, from_warehouse_id: str, to_warehouse_id: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="inventory.transferred",
        source="erp.inventory",
        payload={"item_id": item_id, "from_warehouse_id": from_warehouse_id, "to_warehouse_id": to_warehouse_id},
    )


def emit_inventory_valued(org_id: str, *, valuation_date: str, item_count: int) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="inventory.valued",
        source="erp.inventory",
        payload={"valuation_date": valuation_date, "item_count": item_count},
    )


def emit_inventory_closed(org_id: str, *, period_id: str) -> None:
    platform_event_service.publish(
        org_id=org_id,
        event_type="inventory.closed",
        source="erp.inventory",
        payload={"period_id": period_id},
    )
