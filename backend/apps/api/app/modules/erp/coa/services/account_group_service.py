from __future__ import annotations

from app.modules.erp.coa.repositories.account_group_repository import account_group_repository
from app.modules.erp.coa.services.account_validation_service import account_validation_service


class AccountGroupService:
    def create(
        self,
        org_id: str,
        *,
        group_name: str,
        group_code: str,
        group_type: str,
        nature: str,
        parent_group_id: str | None = None,
        company_id: str | None = None,
    ) -> dict:
        account_validation_service.validate_group(group_type=group_type, nature=nature)
        row = account_group_repository.create(
            org_id,
            group_name=group_name,
            group_code=group_code,
            group_type=group_type,
            nature=nature,
            parent_group_id=parent_group_id,
            company_id=company_id,
        )
        try:
            from app.modules.platform.governance.services.audit_service import audit_service
            from app.modules.platform.governance.utils.object_ref import format_object_ref

            audit_service.record(
                org_id=org_id,
                actor_type="system",
                actor_id="erp.coa",
                action="erp.account_group.created",
                object_ref=format_object_ref("erp", "account_group", str(row.get("id"))),
                payload={"group_code": group_code, "group_name": group_name, "group_type": group_type, "nature": nature},
                entity_type="account_group",
                entity_id=str(row.get("id")),
                source_service="erp.coa",
            )
        except Exception:
            pass
        return row

    def list(self, org_id: str, *, company_id: str | None = None) -> list[dict]:
        return account_group_repository.list(org_id, company_id=company_id)

    def update(self, org_id: str, *, group_id: str, group_name: str, parent_group_id: str | None) -> dict:
        # Enforce type immutability by only allowing name/parent changes.
        # Loop prevention best-effort
        chain = {r["id"]: r.get("parent_group_id") for r in account_group_repository.list(org_id, limit=1000)}
        account_validation_service.ensure_no_hierarchy_loop(node_id=group_id, parent_id=parent_group_id, parent_chain=chain)
        row = account_group_repository.update_name(org_id, group_id=group_id, group_name=group_name, parent_group_id=parent_group_id)
        return row


account_group_service = AccountGroupService()

