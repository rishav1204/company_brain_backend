from __future__ import annotations

from app.modules.erp.coa.repositories.account_repository import account_repository
from app.modules.erp.coa.repositories.account_usage_repository import account_usage_repository
from app.modules.erp.coa.services.account_validation_service import account_validation_service


class AccountService:
    def create(
        self,
        org_id: str,
        *,
        account_code: str,
        account_name: str,
        account_type: str,
        group_id: str,
        parent_account_id: str | None,
        is_postable: bool,
        currency_code: str = "INR",
        company_id: str | None = None,
    ) -> dict:
        account_validation_service.validate_account(
            account_type=account_type, is_postable=bool(is_postable), parent_account_id=parent_account_id
        )
        row = account_repository.create(
            org_id,
            account_code=account_code,
            account_name=account_name,
            account_type=account_type,
            group_id=group_id,
            parent_account_id=parent_account_id,
            is_postable=bool(is_postable),
            currency_code=currency_code or "INR",
            company_id=company_id,
        )
        try:
            from app.modules.erp.coa.events.coa_events import emit_account_created

            emit_account_created(org_id, account_id=str(row.get("id") or ""), metadata={"account_code": account_code})
        except Exception:
            pass
        try:
            from app.modules.platform.governance.services.audit_service import audit_service
            from app.modules.platform.governance.utils.object_ref import format_object_ref

            audit_service.record(
                org_id=org_id,
                actor_type="system",
                actor_id="erp.coa",
                action="erp.account.created",
                object_ref=format_object_ref("erp", "account", str(row.get("id"))),
                payload={
                    "account_code": account_code,
                    "account_name": account_name,
                    "account_type": account_type,
                    "group_id": group_id,
                    "is_postable": bool(is_postable),
                },
                entity_type="account",
                entity_id=str(row.get("id")),
                source_service="erp.coa",
            )
        except Exception:
            pass
        return row

    def list(self, org_id: str, *, company_id: str | None = None) -> list[dict]:
        return account_repository.list(org_id, company_id=company_id)

    def update(self, org_id: str, *, account_id: str, account_name: str, parent_account_id: str | None) -> dict:
        # Enforce type immutability by only allowing name/parent changes.
        chain = {r["id"]: r.get("parent_account_id") for r in account_repository.list(org_id, limit=2000)}
        account_validation_service.ensure_no_hierarchy_loop(node_id=account_id, parent_id=parent_account_id, parent_chain=chain)
        row = account_repository.update_name_and_parent(
            org_id, account_id=account_id, account_name=account_name, parent_account_id=parent_account_id
        )
        try:
            from app.modules.erp.coa.events.coa_events import emit_account_updated

            emit_account_updated(org_id, account_id=account_id, changes={"account_name": account_name, "parent_account_id": parent_account_id})
        except Exception:
            pass
        return row

    def deactivate(self, org_id: str, *, account_id: str) -> dict:
        usage = account_usage_repository.get_or_default(org_id, account_id=account_id)
        account_validation_service.can_deactivate_account(
            has_balance=bool(usage.get("has_balance")), used_in_journals=bool(usage.get("used_in_journals"))
        )
        row = account_repository.deactivate(org_id, account_id=account_id)
        try:
            from app.modules.erp.coa.events.coa_events import emit_account_updated

            emit_account_updated(org_id, account_id=account_id, changes={"is_active": False})
        except Exception:
            pass
        return row


account_service = AccountService()

