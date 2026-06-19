from __future__ import annotations

from app.modules.erp.inventory.events.inventory_events import (
    emit_inventory_adjusted,
    emit_inventory_issued,
    emit_inventory_received,
    emit_inventory_transferred,
    emit_inventory_valued,
)


def emit_received(org_id: str, **kwargs) -> None:
    emit_inventory_received(org_id, **kwargs)


def emit_issued(org_id: str, **kwargs) -> None:
    emit_inventory_issued(org_id, **kwargs)


def emit_adjusted(org_id: str, **kwargs) -> None:
    emit_inventory_adjusted(org_id, **kwargs)


def emit_transferred(org_id: str, **kwargs) -> None:
    emit_inventory_transferred(org_id, **kwargs)


def emit_valued(org_id: str, **kwargs) -> None:
    emit_inventory_valued(org_id, **kwargs)
