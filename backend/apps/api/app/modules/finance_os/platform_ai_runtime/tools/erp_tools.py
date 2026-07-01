from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.tools.registry import ErpToolRegistry


def register_custom_tools(registry: ErpToolRegistry) -> None:
    """Hand-tuned handlers that need special params or stubs not covered by catalog adapters."""
    registry.register("procurement", "confirm_grn", _procurement_confirm_grn, policy_action="procurement.confirm_grn")
    registry.register("procurement", "cancel_grn", _procurement_cancel_grn, policy_action="procurement.cancel_grn")
    registry.register("inventory", "receive", _inventory_receive, policy_action="inventory.receive", compensation="inventory.reverse_receipt")
    registry.register("inventory", "deactivate_item", _inventory_deactivate_item, policy_action="inventory.deactivate_item")


def _procurement_confirm_grn(org_id: str, params: dict, attrs, roles, human_approved: bool) -> dict:
    if not human_approved:
        return {"status": "pending_approval", "detail": "approval_required", "target": "procurement"}
    from app.modules.erp.procurement.services.grn_service import grn_service

    grn_id = str(params.get("grn_id") or params.get("entity_id") or "")
    if not grn_id:
        raise ValueError("grn_id required")
    grn = grn_service.confirm(
        org_id,
        grn_id=grn_id,
        actor_id=str((attrs or {}).get("user_id") or "platform-runtime"),
        skip_workflow_check=True,
    )
    return {"status": "completed", "target": "procurement", "detail": "confirm_grn", "entity_id": grn.get("id"), "grn": grn}


def _procurement_cancel_grn(org_id: str, params: dict, attrs, roles, human_approved: bool) -> dict:
    if not human_approved:
        return {"status": "pending_approval", "detail": "approval_required", "target": "procurement"}
    return {"status": "completed", "target": "procurement", "detail": "cancel_grn", "note": "GRN cancellation requires manual review"}


def _inventory_receive(org_id: str, params: dict, attrs, roles, human_approved: bool) -> dict:
    if not human_approved:
        return {"status": "pending_approval", "detail": "approval_required", "target": "inventory", "draft": params}
    from app.modules.erp.inventory.services.receipt_service import receipt_service

    movement = receipt_service.receive_manual(
        org_id,
        item_id=str(params["item_id"]),
        warehouse_id=str(params["warehouse_id"]),
        quantity=float(params["quantity"]),
        unit_cost=float(params.get("unit_cost") or 0),
        actor_id=str((attrs or {}).get("user_id") or "platform-runtime"),
        post_journal=bool(params.get("post_journal", True)),
    )
    return {"status": "completed", "target": "inventory", "detail": "receive", "movement": movement}


def _inventory_deactivate_item(org_id: str, params: dict, attrs, roles, human_approved: bool) -> dict:
    if not human_approved:
        return {"status": "pending_approval", "detail": "approval_required", "target": "inventory"}
    return {"status": "completed", "target": "inventory", "detail": "deactivate_item", "note": "Item deactivation stub — manual review required"}
