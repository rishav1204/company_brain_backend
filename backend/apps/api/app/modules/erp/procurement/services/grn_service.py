from __future__ import annotations

from datetime import datetime, timezone

from app.modules.erp.procurement.repositories.grn_repository import grn_repository
from app.modules.erp.procurement.repositories.po_repository import po_repository
from app.modules.erp.procurement.validators.grn_validator import ensure_confirmable, validate_received_qty
from app.modules.erp.procurement.validators.po_validator import ensure_receivable
from app.modules.erp.procurement.events.procurement_events import emit_grn_created, emit_grn_confirmed


class GrnService:
    def _grn_number(self) -> str:
        return f"GRN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    def _audit(self, org_id: str, *, action: str, entity_id: str, actor_id: str | None, details: dict) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_id=actor_id,
                action=action,
                resource_type="goods_receipt",
                resource_id=entity_id,
                details=details,
            )
        except Exception:
            pass

    def maybe_accrue(self, org_id: str, *, grn_id: str) -> dict:
        """Delegate GRN inventory receipt when M18 module is active."""
        try:
            from app.modules.erp.inventory.services.receipt_service import receipt_service

            movements = receipt_service.receive_from_grn(org_id, grn_id=grn_id)
            return {"accrual_required": bool(movements), "grn_id": grn_id, "movement_count": len(movements)}
        except Exception:
            return {"accrual_required": False, "grn_id": grn_id}

    def create(
        self,
        org_id: str,
        *,
        po_id: str,
        received_by: str,
        received_date: str | None = None,
        items: list[dict],
    ) -> dict:
        po = po_repository.get(org_id, po_id=po_id)
        if not po:
            raise ValueError("PO not found")
        ensure_receivable(str(po.get("status")))
        if str(po.get("created_by") or "") == received_by:
            pass  # maker-checker hint only
        po_items = {str(i["id"]): i for i in po_repository.list_items(org_id, po_id=po_id)}
        for line in items:
            po_item_id = str(line.get("po_item_id") or "")
            po_item = po_items.get(po_item_id)
            if not po_item:
                raise ValueError(f"Invalid PO item {po_item_id}")
            validate_received_qty(
                ordered=float(po_item.get("quantity") or 0),
                already_received=float(po_item.get("received_quantity") or 0),
                incoming=float(line.get("received_quantity") or 0),
            )
        grn = grn_repository.create(
            org_id,
            grn_number=self._grn_number(),
            po_id=po_id,
            received_by=received_by,
            received_date=received_date,
        )
        grn_id = str(grn["id"])
        for line in items:
            grn_repository.add_item(
                org_id,
                grn_id=grn_id,
                po_item_id=str(line["po_item_id"]),
                received_quantity=float(line.get("received_quantity") or 0),
                accepted_quantity=float(line.get("accepted_quantity") or line.get("received_quantity") or 0),
                rejected_quantity=float(line.get("rejected_quantity") or 0),
            )
        grn = grn_repository.get(org_id, grn_id=grn_id) or grn
        grn["items"] = grn_repository.list_items(org_id, grn_id=grn_id)
        emit_grn_created(org_id, grn_id=grn_id, grn_number=str(grn.get("grn_number")), po_id=po_id)
        self._audit(org_id, action="grn.created", entity_id=grn_id, actor_id=received_by, details={"po_id": po_id})
        return grn

    def get(self, org_id: str, *, grn_id: str) -> dict | None:
        grn = grn_repository.get(org_id, grn_id=grn_id)
        if grn:
            grn["items"] = grn_repository.list_items(org_id, grn_id=grn_id)
        return grn

    def list_for_po(self, org_id: str, *, po_id: str) -> list[dict]:
        return grn_repository.list_for_po(org_id, po_id=po_id)

    def submit_for_confirmation(self, org_id: str, *, grn_id: str, actor_id: str) -> dict:
        grn = grn_repository.get(org_id, grn_id=grn_id)
        if not grn:
            raise ValueError("GRN not found")
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "goods_receipt",
                    "entity_id": grn_id,
                    "started_by": actor_id,
                    "metadata": {"grn_id": grn_id, "po_id": grn.get("po_id")},
                },
            )
        except Exception:
            pass
        return grn

    def mark_workflow_approved(self, org_id: str, *, grn_id: str) -> dict:
        return grn_repository.set_status(org_id, grn_id=grn_id, status="draft", workflow_approved=True)

    def confirm(self, org_id: str, *, grn_id: str, actor_id: str, skip_workflow_check: bool = False) -> dict:
        grn = grn_repository.get(org_id, grn_id=grn_id)
        if not grn:
            raise ValueError("GRN not found")
        ensure_confirmable(str(gr.get("status")))
        if not skip_workflow_check and not grn.get("workflow_approved"):
            raise ValueError("GRN workflow confirmation required")
        po_id = str(grn.get("po_id"))
        for item in grn_repository.list_items(org_id, grn_id=grn_id):
            po_item = po_repository.list_items(org_id, po_id=po_id)
            po_item_map = {str(p["id"]): p for p in po_item}
            pi = po_item_map.get(str(item.get("po_item_id")))
            if pi:
                new_received = float(pi.get("received_quantity") or 0) + float(item.get("accepted_quantity") or 0)
                po_repository.update_received_qty(org_id, po_item_id=str(pi["id"]), received_quantity=new_received)
        po_repository.rollup_receipt_status(org_id, po_id=po_id)
        updated = grn_repository.set_status(org_id, grn_id=grn_id, status="confirmed", workflow_approved=True)
        self.maybe_accrue(org_id, grn_id=grn_id)
        emit_grn_confirmed(org_id, grn_id=grn_id, grn_number=str(grn.get("grn_number")), po_id=po_id)
        self._audit(org_id, action="grn.confirmed", entity_id=grn_id, actor_id=actor_id, details={"po_id": po_id})
        return updated


grn_service = GrnService()
