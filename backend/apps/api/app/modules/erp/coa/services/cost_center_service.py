from __future__ import annotations

from app.modules.erp.coa.repositories.cost_center_repository import cost_center_repository
from app.modules.erp.coa.services.account_validation_service import account_validation_service


class CostCenterService:
    def create(
        self,
        org_id: str,
        *,
        cost_center_code: str,
        cost_center_name: str,
        parent_cost_center_id: str | None,
        company_id: str | None = None,
    ) -> dict:
        # Hierarchy loop prevention (best-effort using current chain)
        chain = {r["id"]: r.get("parent_cost_center_id") for r in cost_center_repository.list(org_id, company_id=company_id)}
        account_validation_service.ensure_no_hierarchy_loop(
            node_id="new_cost_center", parent_id=parent_cost_center_id, parent_chain=chain
        )
        row = cost_center_repository.create(
            org_id,
            cost_center_code=cost_center_code,
            cost_center_name=cost_center_name,
            parent_cost_center_id=parent_cost_center_id,
            company_id=company_id,
        )
        # Audit trail
        try:
            from app.modules.platform.governance.services.audit_service import audit_service
            from app.modules.platform.governance.utils.object_ref import format_object_ref

            audit_service.record(
                org_id=org_id,
                actor_type="system",
                actor_id="erp.coa",
                action="erp.cost_center.created",
                object_ref=format_object_ref("erp", "cost_center", str(row.get("id"))),
                payload={"cost_center_code": cost_center_code, "cost_center_name": cost_center_name},
                entity_type="cost_center",
                entity_id=str(row.get("id")),
                source_service="erp.coa",
            )
        except Exception:
            pass
        return row

    def list(self, org_id: str, *, company_id: str | None = None) -> list[dict]:
        return cost_center_repository.list(org_id, company_id=company_id)

    def deactivate(self, org_id: str, *, cost_center_id: str) -> dict:
        row = cost_center_repository.deactivate(org_id, cost_center_id=cost_center_id)
        try:
            from app.modules.platform.governance.services.audit_service import audit_service
            from app.modules.platform.governance.utils.object_ref import format_object_ref

            audit_service.record(
                org_id=org_id,
                actor_type="system",
                actor_id="erp.coa",
                action="erp.cost_center.deactivated",
                object_ref=format_object_ref("erp", "cost_center", str(cost_center_id)),
                payload={"is_active": False},
                entity_type="cost_center",
                entity_id=str(cost_center_id),
                source_service="erp.coa",
            )
        except Exception:
            pass
        return row

    def update(self, org_id: str, *, cost_center_id: str, cost_center_name: str, parent_cost_center_id: str | None) -> dict:
        chain = {r["id"]: r.get("parent_cost_center_id") for r in cost_center_repository.list(org_id, limit=2000)}
        account_validation_service.ensure_no_hierarchy_loop(
            node_id=cost_center_id, parent_id=parent_cost_center_id, parent_chain=chain
        )
        return cost_center_repository.update_name_and_parent(
            org_id,
            cost_center_id=cost_center_id,
            cost_center_name=cost_center_name,
            parent_cost_center_id=parent_cost_center_id,
        )


cost_center_service = CostCenterService()

