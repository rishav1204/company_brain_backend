from __future__ import annotations

from datetime import datetime, timezone

from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository
from app.modules.erp.procurement.repositories.po_repository import po_repository
from app.modules.erp.procurement.repositories.requisition_repository import requisition_repository
from app.modules.erp.procurement.services.budget_check_service import budget_check_service
from app.modules.erp.procurement.services.procurement_policy_service import procurement_policy_service
from app.modules.erp.procurement.workflows.po_approval_workflow import po_workflow_metadata
from app.modules.erp.procurement.validators.po_validator import (
    ensure_cancellable,
    ensure_editable,
    ensure_sendable,
    ensure_submittable,
)
from app.modules.erp.procurement.events.procurement_events import emit_po_created, emit_po_approved, emit_po_sent


class PoService:
    def _po_number(self) -> str:
        return f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    def _audit(self, org_id: str, *, action: str, entity_id: str, actor_id: str | None, details: dict) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_id=actor_id,
                action=action,
                resource_type="purchase_order",
                resource_id=entity_id,
                details=details,
            )
        except Exception:
            pass

    def create(
        self,
        org_id: str,
        *,
        vendor_id: str,
        pr_id: str | None = None,
        po_date: str | None = None,
        expected_delivery_date: str | None = None,
        company_id: str | None = None,
        created_by: str | None = None,
        items: list[dict] | None = None,
        gst_amount: float = 0,
    ) -> dict:
        vendor = vendor_repository.get(org_id, vendor_id=vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")
        procurement_policy_service.ensure_vendor_allowed(org_id, vendor=vendor)
        po = po_repository.create(
            org_id,
            po_number=self._po_number(),
            vendor_id=vendor_id,
            pr_id=pr_id,
            po_date=po_date,
            expected_delivery_date=expected_delivery_date,
            company_id=company_id,
            created_by=created_by,
        )
        po_id = str(po["id"])
        for item in items or []:
            po_repository.add_item(
                org_id,
                po_id=po_id,
                item_name=str(item.get("item_name") or "Item"),
                quantity=float(item.get("quantity") or 1),
                unit_price=float(item.get("unit_price") or 0),
                hsn_sac=item.get("hsn_sac"),
            )
        po = po_repository.get(org_id, po_id=po_id) or po
        po["items"] = po_repository.list_items(org_id, po_id=po_id)
        emit_po_created(
            org_id,
            po_id=po_id,
            po_number=str(po.get("po_number")),
            vendor_id=vendor_id,
            amount=float(po.get("total_amount") or 0),
        )
        self._audit(org_id, action="po.created", entity_id=po_id, actor_id=created_by, details={"vendor_id": vendor_id})
        return po

    def create_from_pr(
        self,
        org_id: str,
        *,
        pr_id: str,
        vendor_id: str,
        created_by: str,
        company_id: str | None = None,
        items: list[dict],
        gst_amount: float = 0,
    ) -> dict:
        po_items = [
            {
                "item_name": i.get("item_name"),
                "quantity": i.get("quantity"),
                "unit_price": i.get("unit_price"),
            }
            for i in items
        ]
        return self.create(
            org_id,
            vendor_id=vendor_id,
            pr_id=pr_id,
            company_id=company_id,
            created_by=created_by,
            items=po_items,
            gst_amount=gst_amount,
        )

    def get(self, org_id: str, *, po_id: str) -> dict | None:
        po = po_repository.get(org_id, po_id=po_id)
        if po:
            po["items"] = po_repository.list_items(org_id, po_id=po_id)
        return po

    def list(self, org_id: str, *, status: str | None = None, vendor_id: str | None = None) -> list[dict]:
        return po_repository.list(org_id, status=status, vendor_id=vendor_id)

    def submit_for_approval(self, org_id: str, *, po_id: str, actor_id: str) -> dict:
        po = po_repository.get(org_id, po_id=po_id)
        if not po:
            raise ValueError("PO not found")
        ensure_submittable(str(po.get("status")))
        amount = float(po.get("total_amount") or 0)
        updated = po_repository.set_status(org_id, po_id=po_id, status="pending_approval")
        policy = procurement_policy_service.get_active(org_id)
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "purchase_order",
                    "entity_id": po_id,
                    "amount": amount,
                    "started_by": actor_id,
                    "metadata": po_workflow_metadata(
                        amount,
                        vendor_id=str(po.get("vendor_id")),
                        po_id=po_id,
                        thresholds=policy.get("approval_thresholds"),
                    ),
                },
            )
        except Exception:
            pass
        self._audit(org_id, action="po.submitted", entity_id=po_id, actor_id=actor_id, details={"amount": amount})
        return updated

    def mark_workflow_approved(self, org_id: str, *, po_id: str) -> dict:
        return po_repository.set_status(org_id, po_id=po_id, status="pending_approval", workflow_approved=True)

    def approve(self, org_id: str, *, po_id: str, approver_id: str, skip_workflow_check: bool = False) -> dict:
        po = po_repository.get(org_id, po_id=po_id)
        if not po:
            raise ValueError("PO not found")
        if str(po.get("status")) not in {"pending_approval", "draft"}:
            raise ValueError(f"PO cannot be approved from status {po.get('status')}")
        if not skip_workflow_check and not po.get("workflow_approved"):
            raise ValueError("PO workflow approval required")
        from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker

        try:
            enforce_maker_checker(created_by=str(po.get("created_by") or ""), actor_user_id=approver_id, org_id=org_id)
        except MakerCheckerViolation as exc:
            raise ValueError(str(exc)) from exc
        amount = float(po.get("total_amount") or 0)
        pr = requisition_repository.get(org_id, pr_id=str(po["pr_id"])) if po.get("pr_id") else None
        cost_center = pr.get("cost_center_id") if pr else None
        budget_check_service.commit_spend(org_id, cost_center_id=cost_center, amount=amount)
        updated = po_repository.set_status(
            org_id, po_id=po_id, status="approved", approved_by=approver_id, workflow_approved=True
        )
        emit_po_approved(org_id, po_id=po_id, po_number=str(po.get("po_number")))
        self._audit(org_id, action="po.approved", entity_id=po_id, actor_id=approver_id, details={})
        return updated

    def send(self, org_id: str, *, po_id: str, actor_id: str) -> dict:
        po = po_repository.get(org_id, po_id=po_id)
        if not po:
            raise ValueError("PO not found")
        ensure_sendable(str(po.get("status")))
        updated = po_repository.set_status(org_id, po_id=po_id, status="sent", sent_at=True)
        emit_po_sent(org_id, po_id=po_id, po_number=str(po.get("po_number")))
        self._audit(org_id, action="po.sent", entity_id=po_id, actor_id=actor_id, details={})
        return updated

    def close(self, org_id: str, *, po_id: str, actor_id: str) -> dict:
        po = po_repository.get(org_id, po_id=po_id)
        if not po:
            raise ValueError("PO not found")
        return po_repository.set_status(org_id, po_id=po_id, status="closed")

    def cancel(self, org_id: str, *, po_id: str, actor_id: str) -> dict:
        po = po_repository.get(org_id, po_id=po_id)
        if not po:
            raise ValueError("PO not found")
        ensure_cancellable(str(po.get("status")))
        if str(po.get("status")) == "approved":
            pr = requisition_repository.get(org_id, pr_id=str(po["pr_id"])) if po.get("pr_id") else None
            budget_check_service.release_spend(
                org_id,
                cost_center_id=pr.get("cost_center_id") if pr else None,
                amount=float(po.get("total_amount") or 0),
            )
        return po_repository.set_status(org_id, po_id=po_id, status="cancelled")


po_service = PoService()
