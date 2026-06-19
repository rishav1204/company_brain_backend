from __future__ import annotations

from datetime import datetime, timezone

from app.modules.erp.procurement.repositories.requisition_repository import requisition_repository
from app.modules.erp.procurement.repositories.po_repository import po_repository
from app.modules.erp.procurement.services.budget_check_service import budget_check_service
from app.modules.erp.procurement.services.approval_service import approval_service
from app.modules.erp.procurement.validators.requisition_validator import (
    ensure_approvable,
    ensure_cancellable,
    ensure_convertible,
    ensure_submittable,
)
from app.modules.erp.procurement.events.procurement_events import emit_pr_created, emit_pr_approved


class RequisitionService:
    def _pr_number(self) -> str:
        return f"PR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    def _audit(self, org_id: str, *, action: str, entity_id: str, actor_id: str | None, details: dict) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_id=actor_id,
                action=action,
                resource_type="purchase_requisition",
                resource_id=entity_id,
                details=details,
            )
        except Exception:
            pass

    def create(
        self,
        org_id: str,
        *,
        requester_id: str | None = None,
        department_id: str | None = None,
        cost_center_id: str | None = None,
        required_date: str | None = None,
        description: str | None = None,
        company_id: str | None = None,
        created_by: str | None = None,
        items: list[dict] | None = None,
    ) -> dict:
        pr = requisition_repository.create(
            org_id,
            pr_number=self._pr_number(),
            requester_id=requester_id or created_by,
            department_id=department_id,
            cost_center_id=cost_center_id,
            required_date=required_date,
            description=description,
            company_id=company_id,
            created_by=created_by,
        )
        pr_id = str(pr["id"])
        for item in items or []:
            requisition_repository.add_item(
                org_id,
                pr_id=pr_id,
                item_name=str(item.get("item_name") or "Item"),
                quantity=float(item.get("quantity") or 1),
                unit_price=float(item.get("unit_price") or 0),
                description=item.get("description"),
                expense_account_id=item.get("expense_account_id"),
            )
        pr = requisition_repository.get(org_id, pr_id=pr_id) or pr
        pr["items"] = requisition_repository.list_items(org_id, pr_id=pr_id)
        emit_pr_created(org_id, pr_id=pr_id, pr_number=str(pr.get("pr_number")), amount=float(pr.get("total_amount") or 0))
        self._audit(org_id, action="pr.created", entity_id=pr_id, actor_id=created_by, details={"pr_number": pr.get("pr_number")})
        return pr

    def get(self, org_id: str, *, pr_id: str) -> dict | None:
        pr = requisition_repository.get(org_id, pr_id=pr_id)
        if pr:
            pr["items"] = requisition_repository.list_items(org_id, pr_id=pr_id)
        return pr

    def list(self, org_id: str, *, status: str | None = None) -> list[dict]:
        return requisition_repository.list(org_id, status=status)

    def submit(self, org_id: str, *, pr_id: str, actor_id: str) -> dict:
        pr = requisition_repository.get(org_id, pr_id=pr_id)
        if not pr:
            raise ValueError("PR not found")
        ensure_submittable(str(pr.get("status")))
        amount = float(pr.get("total_amount") or 0)
        budget = budget_check_service.check_pr(org_id, cost_center_id=pr.get("cost_center_id"), amount=amount)
        if budget.get("enforced") and not budget.get("sufficient"):
            raise ValueError(f"Budget insufficient: shortfall {budget.get('shortfall')}")
        updated = requisition_repository.set_status(org_id, pr_id=pr_id, status="submitted")
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "purchase_requisition",
                    "entity_id": pr_id,
                    "amount": amount,
                    "started_by": actor_id,
                    "metadata": approval_service.build_pr_metadata(org_id, pr_id=pr_id, amount=amount),
                },
            )
        except Exception:
            pass
        self._audit(org_id, action="pr.submitted", entity_id=pr_id, actor_id=actor_id, details={"budget": budget})
        return updated

    def mark_workflow_approved(self, org_id: str, *, pr_id: str) -> dict:
        return requisition_repository.set_status(org_id, pr_id=pr_id, status="submitted", workflow_approved=True)

    def approve(self, org_id: str, *, pr_id: str, approver_id: str, skip_workflow_check: bool = False) -> dict:
        pr = requisition_repository.get(org_id, pr_id=pr_id)
        if not pr:
            raise ValueError("PR not found")
        ensure_approvable(str(pr.get("status")))
        if not skip_workflow_check and not pr.get("workflow_approved"):
            raise ValueError("PR workflow approval required")
        from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker

        try:
            enforce_maker_checker(created_by=str(pr.get("created_by") or ""), actor_user_id=approver_id, org_id=org_id)
        except MakerCheckerViolation as exc:
            raise ValueError(str(exc)) from exc
        updated = requisition_repository.set_status(
            org_id, pr_id=pr_id, status="approved", approved_by=approver_id, workflow_approved=True
        )
        emit_pr_approved(org_id, pr_id=pr_id, pr_number=str(pr.get("pr_number")))
        self._audit(org_id, action="pr.approved", entity_id=pr_id, actor_id=approver_id, details={})
        return updated

    def cancel(self, org_id: str, *, pr_id: str, actor_id: str) -> dict:
        pr = requisition_repository.get(org_id, pr_id=pr_id)
        if not pr:
            raise ValueError("PR not found")
        ensure_cancellable(str(pr.get("status")))
        return requisition_repository.set_status(org_id, pr_id=pr_id, status="cancelled")

    def convert_to_po(
        self,
        org_id: str,
        *,
        pr_id: str,
        vendor_id: str,
        actor_id: str,
        gst_amount: float = 0,
    ) -> dict:
        from app.modules.erp.procurement.services.po_service import po_service

        pr = requisition_repository.get(org_id, pr_id=pr_id)
        if not pr:
            raise ValueError("PR not found")
        ensure_convertible(str(pr.get("status")))
        items = requisition_repository.list_items(org_id, pr_id=pr_id)
        po = po_service.create_from_pr(
            org_id,
            pr_id=pr_id,
            vendor_id=vendor_id,
            created_by=actor_id,
            company_id=pr.get("company_id"),
            items=items,
            gst_amount=gst_amount,
        )
        requisition_repository.set_status(org_id, pr_id=pr_id, status="converted_to_po")
        return po


requisition_service = RequisitionService()
